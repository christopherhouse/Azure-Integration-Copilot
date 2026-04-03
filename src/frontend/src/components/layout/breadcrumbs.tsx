"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { Fragment } from "react";
import { useProject } from "@/hooks/use-projects";

/**
 * Extract a project ID from path segments when the URL matches the pattern
 * /dashboard/projects/:projectId[/...].
 */
function getProjectIdFromSegments(segments: string[]): string | null {
  if (
    segments[0] === "dashboard" &&
    segments[1] === "projects" &&
    segments[2]
  ) {
    return segments[2];
  }
  return null;
}

/**
 * Breadcrumb navigation derived from the current URL path.
 *
 * Segments named "dashboard" are labelled "Home".  When the URL contains a
 * project ID (e.g. /dashboard/projects/:projectId), the project name is
 * fetched from the API and shown in place of the raw GUID.  Other segments
 * are title-cased.
 */
export function Breadcrumbs() {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);
  const projectId = getProjectIdFromSegments(segments);

  // Always call the hook; `enabled` is false when there is no project ID.
  const { data: project } = useProject(projectId ?? "");

  const crumbs = segments.map((segment, index) => {
    const href = "/" + segments.slice(0, index + 1).join("/");
    let label: string;

    if (segment === "dashboard") {
      label = "Home";
    } else if (projectId && segment === projectId) {
      label = project?.name ?? "…";
    } else {
      label = segment.charAt(0).toUpperCase() + segment.slice(1);
    }

    return { href, label };
  });

  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-sm">
      {crumbs.map((crumb, i) => (
        <Fragment key={crumb.href}>
          {i > 0 && (
            <ChevronRight className="size-3.5 text-muted-foreground" />
          )}
          {i === crumbs.length - 1 ? (
            <span className="font-medium text-foreground">{crumb.label}</span>
          ) : (
            <Link
              href={crumb.href}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              {crumb.label}
            </Link>
          )}
        </Fragment>
      ))}
    </nav>
  );
}
