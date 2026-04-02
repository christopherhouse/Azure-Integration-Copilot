import type { AuthOptions } from "next-auth";
import type { OAuthConfig } from "next-auth/providers/oauth";
import CredentialsProvider from "next-auth/providers/credentials";

/**
 * NextAuth.js configuration.
 *
 * - In production, Microsoft Entra External ID (CIAM) is the primary provider.
 * - In development (`NODE_ENV !== "production"`), a credentials provider
 *   allows login without a real CIAM tenant.
 *
 * The access token is persisted in the JWT and surfaced on the session so
 * the API client can attach it as a Bearer token.
 */

/**
 * Build an OIDC provider for Microsoft Entra External ID (CIAM) when the
 * required environment variables are present.  Returns an empty array when
 * any required variable is missing so the providers list remains valid.
 */
function buildEntraCiamProvider(): OAuthConfig<Record<string, unknown>>[] {
  const subdomain = process.env.ENTRA_CIAM_TENANT_SUBDOMAIN;
  const clientId = process.env.ENTRA_CIAM_FRONTEND_CLIENT_ID;
  const clientSecret = process.env.ENTRA_CIAM_FRONTEND_CLIENT_SECRET;
  const backendClientId = process.env.ENTRA_CIAM_CLIENT_ID;

  if (!subdomain || !clientId || !clientSecret || !backendClientId) {
    return [];
  }

  // Use type "oauth" — NextAuth v4's callback handler only supports "oauth",
  // "email", and "credentials".  Using "oidc" causes the callback to fail with
  // "Callback for provider type oidc not supported".  The wellKnown URL
  // automatically enables idToken validation via openid-client.
  return [
    {
      id: "azure-ad",
      name: "Microsoft Entra",
      type: "oauth",
      wellKnown: `https://${subdomain}.ciamlogin.com/${subdomain}.onmicrosoft.com/v2.0/.well-known/openid-configuration`,
      clientId,
      clientSecret,
      client: {
        token_endpoint_auth_method: "client_secret_post",
      },
      authorization: {
        params: {
          scope: `openid profile email offline_access api://${backendClientId}/access_as_user`,
        },
      },
      checks: ["pkce", "state"],
      profile(profile: Record<string, unknown>) {
        const emailsArr = Array.isArray(profile.emails)
          ? (profile.emails as string[])
          : [];
        return {
          id: (profile.oid as string) || (profile.sub as string),
          name: profile.name as string,
          email:
            (profile.email as string) ||
            emailsArr[0] ||
            (profile.preferred_username as string),
        };
      },
    } as OAuthConfig<Record<string, unknown>>,
  ];
}

export const authOptions: AuthOptions = {
  providers: [
    // ── Microsoft Entra External ID (CIAM) ─────────────────────────
    ...buildEntraCiamProvider(),

    // ── Development credentials provider ───────────────────────────
    ...(process.env.NODE_ENV !== "production"
      ? [
          CredentialsProvider({
            id: "dev-credentials",
            name: "Dev Login",
            credentials: {
              email: {
                label: "Email",
                type: "email",
                placeholder: "dev@example.com",
              },
              password: {
                label: "Password",
                type: "password",
                placeholder: "password",
              },
            },
            async authorize(credentials) {
              // Accept any non-empty email + password combination in dev mode.
              if (credentials?.email && credentials?.password) {
                return {
                  id: "dev-user-1",
                  name: "Dev User",
                  email: credentials.email,
                };
              }
              return null;
            },
          }),
        ]
      : []),
  ],

  session: { strategy: "jwt" },

  pages: {
    signIn: "/login",
  },

  callbacks: {
    async jwt({ token, account }) {
      // Persist the access_token from the provider on first sign-in.
      if (account?.access_token) {
        token.accessToken = account.access_token;
      }
      // For the dev credentials provider, mint a placeholder token.
      if (account?.provider === "dev-credentials" && !token.accessToken) {
        token.accessToken = "dev-only-placeholder-token";
      }
      return token;
    },

    async session({ session, token }) {
      session.accessToken = token.accessToken;
      return session;
    },
  },
};
