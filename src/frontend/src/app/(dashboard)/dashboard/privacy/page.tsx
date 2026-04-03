"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  Shield,
  Lock,
  Eye,
  EyeOff,
  ShieldCheck,
  Database,
  Network,
  KeyRound,
  Users,
  Server,
  Globe,
} from "lucide-react";

function CommitmentItem({
  icon: Icon,
  text,
}: {
  icon: React.ComponentType<{ className?: string }>;
  text: string;
}) {
  return (
    <li className="flex items-start gap-3">
      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
        <Icon className="h-3.5 w-3.5" />
      </span>
      <span className="text-sm leading-relaxed">{text}</span>
    </li>
  );
}

function SecurityFeatureCard({
  icon: Icon,
  title,
  description,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Icon className="h-5 w-5" />
          </span>
          <CardTitle className="text-base">{title}</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-relaxed text-muted-foreground">
          {description}
        </p>
      </CardContent>
    </Card>
  );
}

export default function PrivacyPage() {
  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold">Privacy &amp; Security</h1>
        <p className="text-sm text-muted-foreground">
          How Integrisight protects your data and keeps your integration
          artifacts safe.
        </p>
      </div>

      {/* Trust Banner */}
      <Card>
        <CardContent className="flex items-center gap-4 py-5">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
            <ShieldCheck className="h-6 w-6" />
          </span>
          <div>
            <p className="text-sm font-semibold">
              Your data is yours. Always.
            </p>
            <p className="text-sm text-muted-foreground">
              Integrisight is built from the ground up with privacy and security
              as core principles&mdash;not afterthoughts. We believe earning
              your trust starts with transparency.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Data Privacy Commitments */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <Shield className="h-5 w-5" />
            </span>
            <div>
              <CardTitle>Our Data Privacy Commitments</CardTitle>
              <CardDescription>
                Clear, non-negotiable promises about how we handle your data.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <ul className="flex flex-col gap-4">
            <CommitmentItem
              icon={EyeOff}
              text="Your data is never used to train AI models. Your artifacts remain exclusively yours and are never fed into any machine-learning training pipeline."
            />
            <CommitmentItem
              icon={Lock}
              text="Your data is never shared with third parties. We do not disclose, license, or provide your data to any external entity."
            />
            <CommitmentItem
              icon={ShieldCheck}
              text="Your data is never sold. Monetizing customer data is not and will never be part of our business model."
            />
            <CommitmentItem
              icon={Eye}
              text="You retain full ownership of your data. Everything you upload, create, or generate within Integrisight belongs to you."
            />
            <CommitmentItem
              icon={Database}
              text="Your data can be deleted at any time upon request. Contact our team and we will permanently remove all your data from our systems."
            />
          </ul>
        </CardContent>
      </Card>

      <Separator />

      {/* Platform Security Features */}
      <div>
        <h2 className="text-xl font-semibold">Platform Security</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Enterprise-grade security measures that protect your data at every
          layer of the platform.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <SecurityFeatureCard
          icon={Network}
          title="Private Networking"
          description="All backend services communicate over isolated private networks. No internal service is ever exposed to the public internet, drastically reducing the attack surface."
        />
        <SecurityFeatureCard
          icon={KeyRound}
          title="Identity-Based Connections"
          description="Services authenticate to each other using managed identities rather than stored credentials, eliminating the risk of credential leakage or secret sprawl."
        />
        <SecurityFeatureCard
          icon={Globe}
          title="Web Application Firewall"
          description="All incoming traffic passes through an enterprise-grade web application firewall that inspects and filters malicious requests before they reach the application."
        />
        <SecurityFeatureCard
          icon={Shield}
          title="Traffic Filtering &amp; DDoS Protection"
          description="Edge-level traffic inspection and distributed denial-of-service protection ensure the platform remains available even under attack."
        />
        <SecurityFeatureCard
          icon={Lock}
          title="Encrypted Data at Rest &amp; in Transit"
          description="All data is encrypted using industry-standard encryption — TLS 1.2+ for data in transit and AES-256 for data at rest — so your artifacts are protected at every stage."
        />
        <SecurityFeatureCard
          icon={Server}
          title="Secrets Management"
          description="Sensitive configuration is stored in a dedicated secrets vault, never in application code or configuration files. Access to secrets is tightly controlled and audited."
        />
        <SecurityFeatureCard
          icon={Users}
          title="Role-Based Access Control"
          description="Fine-grained permissions ensure that services and users only access what they need. The principle of least privilege is enforced across the entire platform."
        />
        <SecurityFeatureCard
          icon={Database}
          title="Tenant Isolation"
          description="Each customer's data is logically isolated. No cross-tenant data access is possible — your data is invisible to other tenants and vice versa."
        />
      </div>

      <Separator />

      {/* Data Handling */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Eye className="h-5 w-5" />
            </span>
            <div>
              <CardTitle>How We Handle Your Data</CardTitle>
              <CardDescription>
                Transparency about what happens to the artifacts you share with
                Integrisight.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <ul className="flex flex-col gap-4">
            <li className="flex items-start gap-3">
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                <ShieldCheck className="h-3.5 w-3.5" />
              </span>
              <div>
                <p className="text-sm font-medium">
                  Purpose-Limited Processing
                </p>
                <p className="mt-0.5 text-sm text-muted-foreground">
                  Integration artifacts — including API definitions, schemas,
                  workflows, and related files — are processed solely for the
                  purpose of providing you with analysis, insights, and
                  recommendations. They are never repurposed.
                </p>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                <Database className="h-3.5 w-3.5" />
              </span>
              <div>
                <p className="text-sm font-medium">
                  Scoped &amp; Temporary Storage
                </p>
                <p className="mt-0.5 text-sm text-muted-foreground">
                  Processing results are stored only as long as needed and are
                  associated exclusively with your tenant. Data is not retained
                  beyond its useful life.
                </p>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                <EyeOff className="h-3.5 w-3.5" />
              </span>
              <div>
                <p className="text-sm font-medium">No Human Review</p>
                <p className="mt-0.5 text-sm text-muted-foreground">
                  No human reviews your artifacts unless you explicitly request
                  it for support purposes. Automated processing ensures your
                  data stays private.
                </p>
              </div>
            </li>
          </ul>
        </CardContent>
      </Card>

      {/* Footer Note */}
      <p className="pb-4 text-center text-xs text-muted-foreground">
        Have questions about how Integrisight handles your data?{" "}
        <span className="font-medium text-foreground">
          Reach out to our team
        </span>{" "}
        — we&apos;re happy to discuss your security and privacy requirements.
      </p>
    </div>
  );
}
