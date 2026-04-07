"use client";

import { useState } from "react";
import {
  Bot,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  Wrench,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { Analysis } from "@/types/analysis";

interface AnalysisMessageProps {
  analysis: Analysis;
}

/** Renders a single analyst response with verdict, confidence, and tool calls. */
export function AnalysisMessage({ analysis }: AnalysisMessageProps) {
  const [toolsExpanded, setToolsExpanded] = useState(false);

  const hasToolCalls =
    analysis.toolCalls && analysis.toolCalls.length > 0;

  return (
    <div className="flex gap-3">
      <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
        <Bot className="size-4" />
      </div>

      <Card className="flex-1">
        <CardContent className="flex flex-col gap-3 py-3">
          {/* Verdict + confidence */}
          {analysis.verdict && (
            <div className="flex items-center gap-2">
              <VerdictBadge verdict={analysis.verdict} />
              {analysis.confidenceScore != null && (
                <span className="text-xs text-muted-foreground">
                  {Math.round(analysis.confidenceScore * 100)}% confidence
                </span>
              )}
            </div>
          )}

          {/* Response text */}
          {analysis.response && (
            <div className="prose prose-sm max-w-none text-sm text-foreground dark:prose-invert">
              {analysis.response.split("\n").map((line, i) => (
                <p key={i} className="mb-1 last:mb-0">
                  {line || "\u00A0"}
                </p>
              ))}
            </div>
          )}

          {/* Error state */}
          {analysis.status === "failed" && (
            <div className="flex items-center gap-2 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <AlertTriangle className="size-4 shrink-0" />
              <span>
                {analysis.errorMessage ?? "Analysis failed. Please try again."}
              </span>
            </div>
          )}

          {/* Tool calls (expandable) */}
          {hasToolCalls && (
            <div className="border-t border-border pt-2">
              <Button
                variant="ghost"
                size="sm"
                className="h-auto gap-1.5 px-1 py-0.5 text-xs text-muted-foreground"
                onClick={() => setToolsExpanded((prev) => !prev)}
                aria-expanded={toolsExpanded}
                aria-controls="tool-calls-list"
              >
                {toolsExpanded ? (
                  <ChevronDown className="size-3" />
                ) : (
                  <ChevronRight className="size-3" />
                )}
                <Wrench className="size-3" />
                {analysis.toolCalls!.length} tool call
                {analysis.toolCalls!.length !== 1 ? "s" : ""}
              </Button>

              {toolsExpanded && (
                <ul
                  id="tool-calls-list"
                  className="mt-2 flex flex-col gap-2"
                  role="list"
                >
                  {analysis.toolCalls!.map((tc, idx) => (
                    <li
                      key={idx}
                      className="rounded-md bg-muted/50 px-3 py-2 text-xs"
                    >
                      <div className="font-medium text-foreground">
                        {tc.toolName}
                      </div>
                      {Object.keys(tc.arguments).length > 0 && (
                        <pre className="mt-1 overflow-x-auto text-muted-foreground">
                          {JSON.stringify(tc.arguments, null, 2)}
                        </pre>
                      )}
                      {tc.output && (
                        <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-all text-muted-foreground">
                          {typeof tc.output === "string"
                            ? tc.output
                            : JSON.stringify(tc.output, null, 2)}
                        </pre>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function VerdictBadge({ verdict }: { verdict: Analysis["verdict"] }) {
  switch (verdict) {
    case "PASSED":
      return (
        <Badge className="bg-emerald-500/15 text-emerald-700 dark:text-emerald-400">
          Passed
        </Badge>
      );
    case "FAILED":
      return <Badge variant="destructive">Failed</Badge>;
    case "INCONCLUSIVE":
      return <Badge variant="secondary">Inconclusive</Badge>;
    default:
      return null;
  }
}
