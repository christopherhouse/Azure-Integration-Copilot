import type { AuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

/**
 * NextAuth.js configuration.
 *
 * - In production, Azure AD B2C is the primary provider.
 * - In development (`NODE_ENV !== "production"`), a credentials provider
 *   allows login without a real B2C tenant.
 *
 * The access token is persisted in the JWT and surfaced on the session so
 * the API client can attach it as a Bearer token.
 */
export const authOptions: AuthOptions = {
  providers: [
    // ── Azure AD B2C (production) ──────────────────────────────────
    // Uncomment and configure when a real B2C tenant is available:
    // AzureADB2CProvider({
    //   clientId: process.env.AZURE_AD_B2C_CLIENT_ID!,
    //   clientSecret: process.env.AZURE_AD_B2C_CLIENT_SECRET!,
    //   tenantId: process.env.AZURE_AD_B2C_TENANT_ID!,
    //   primaryUserFlow: process.env.AZURE_AD_B2C_PRIMARY_USER_FLOW!,
    //   authorization: { params: { scope: "openid profile email offline_access" } },
    // }),

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
              // Accept any non-empty credentials in dev mode.
              if (credentials?.email) {
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
        token.accessToken = "dev-token";
      }
      return token;
    },

    async session({ session, token }) {
      session.accessToken = token.accessToken;
      return session;
    },
  },
};
