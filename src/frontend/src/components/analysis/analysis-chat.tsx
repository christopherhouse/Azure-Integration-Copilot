"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { Send, Loader2, Bot, User } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { AnalysisMessage } from "@/components/analysis/analysis-message";
import { useCreateAnalysis, useAnalysis } from "@/hooks/use-analysis";
import type { Analysis } from "@/types/analysis";

interface AnalysisChatProps {
  projectId: string;
  /** Optional pre-selected analysis to display. */
  selectedAnalysis?: Analysis | null;
}

const SAMPLE_PROMPTS = [
  "What are the dependencies of my Logic App?",
  "Show me all API connections in this project",
  "Analyze the integration flow and identify potential bottlenecks",
];

export function AnalysisChat({
  projectId,
  selectedAnalysis,
}: AnalysisChatProps) {
  const [prompt, setPrompt] = useState("");
  const [submittedAnalysisId, setSubmittedAnalysisId] = useState<string | null>(null);
  const [showSamplePrompts, setShowSamplePrompts] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const createMutation = useCreateAnalysis(projectId);

  // The active analysis ID is the selected sidebar item, or the one we just submitted
  const activeAnalysisId = useMemo(
    () => selectedAnalysis?.id ?? submittedAnalysisId,
    [selectedAnalysis?.id, submittedAnalysisId],
  );

  // Hide sample prompts when an analysis is selected from history
  useEffect(() => {
    if (selectedAnalysis) {
      setShowSamplePrompts(false);
    }
  }, [selectedAnalysis]);

  // Poll for the active analysis while it's running
  const { data: activeAnalysis } = useAnalysis(
    projectId,
    activeAnalysisId ?? "",
  );

  // Scroll to bottom on new content
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [activeAnalysis]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = prompt.trim();
      if (!trimmed || createMutation.isPending) return;

      setShowSamplePrompts(false);

      createMutation.mutate(trimmed, {
        onSuccess: (analysis) => {
          setSubmittedAnalysisId(analysis.id);
          setPrompt("");
        },
        onError: (err) => {
          toast.error(
            err instanceof Error ? err.message : "Failed to start analysis",
          );
        },
      });
    },
    [prompt, createMutation],
  );

  const handleSamplePromptClick = useCallback((samplePrompt: string) => {
    setPrompt(samplePrompt);
    setShowSamplePrompts(false);
    inputRef.current?.focus();
  }, []);

  const displayedAnalysis = activeAnalysis ?? selectedAnalysis;
  const isRunning =
    displayedAnalysis?.status === "pending" ||
    displayedAnalysis?.status === "running";

  return (
    <div className="flex h-full flex-col">
      {/* Messages area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4"
        role="log"
        aria-label="Analysis conversation"
        aria-live="polite"
      >
        {!displayedAnalysis && !createMutation.isPending && (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-muted-foreground">
            <Bot className="size-12 opacity-40" />
            <p className="text-sm">
              Ask a question about your integration project to start an
              analysis.
            </p>
            {showSamplePrompts && (
              <div className="mt-4 flex flex-col gap-2">
                {SAMPLE_PROMPTS.map((samplePrompt) => (
                  <Button
                    key={samplePrompt}
                    variant="outline"
                    className="justify-start text-left text-sm font-normal"
                    onClick={() => handleSamplePromptClick(samplePrompt)}
                  >
                    {samplePrompt}
                  </Button>
                ))}
              </div>
            )}
          </div>
        )}

        {displayedAnalysis && (
          <div className="mx-auto flex max-w-3xl flex-col gap-4">
            {/* User prompt */}
            <div className="flex gap-3">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                <User className="size-4" />
              </div>
              <Card className="flex-1">
                <CardContent className="py-3">
                  <p className="text-sm whitespace-pre-wrap">
                    {displayedAnalysis.prompt}
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* Analysis response */}
            {isRunning && (
              <div className="flex gap-3">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
                  <Bot className="size-4" />
                </div>
                <Card className="flex-1">
                  <CardContent className="py-3">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Loader2 className="size-4 animate-spin" />
                      <span>Analyzing…</span>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}

            {(displayedAnalysis.status === "completed" ||
              displayedAnalysis.status === "failed") && (
              <AnalysisMessage analysis={displayedAnalysis} />
            )}
          </div>
        )}

        {/* Pending state while mutation fires (before we get an ID back) */}
        {createMutation.isPending && !displayedAnalysis && (
          <div className="mx-auto flex max-w-3xl flex-col gap-4">
            <div className="flex gap-3">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                <User className="size-4" />
              </div>
              <Card className="flex-1">
                <CardContent className="py-3">
                  <p className="text-sm whitespace-pre-wrap">{prompt}</p>
                </CardContent>
              </Card>
            </div>
            <div className="flex gap-3">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
                <Bot className="size-4" />
              </div>
              <Card className="flex-1">
                <CardContent className="py-3">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="size-4 animate-spin" />
                    <span>Analyzing…</span>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="border-t border-border bg-card p-4">
        <form
          onSubmit={handleSubmit}
          className="mx-auto flex max-w-3xl items-center gap-2"
        >
          <label htmlFor="analysis-prompt" className="sr-only">
            Analysis prompt
          </label>
          <Input
            ref={inputRef}
            id="analysis-prompt"
            type="text"
            placeholder="Ask about your integrations…"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={createMutation.isPending}
            autoComplete="off"
            className="flex-1"
          />
          <Button
            type="submit"
            size="icon"
            disabled={!prompt.trim() || createMutation.isPending}
            aria-label="Send analysis prompt"
          >
            {createMutation.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Send className="size-4" />
            )}
          </Button>
        </form>
      </div>
    </div>
  );
}
