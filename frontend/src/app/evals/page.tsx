"use client";

import React, { useState, useEffect } from "react";
import { 
  ArrowLeft, RefreshCw, CheckCircle, XCircle, Shield, AlertTriangle, Clock, 
  Search, Filter, ChevronDown, ChevronUp, Activity, Play
} from "lucide-react";
import Link from "next/link";
import { EvalsResponse, getEvalsData, triggerEvalsRun } from "../../lib/api";

export default function EvalsDashboard() {
  const [evalData, setEvalData] = useState<EvalsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");
  const [runningSuite, setRunningSuite] = useState(false);
  const [runningMsg, setRunningMsg] = useState("");
  
  // Filtering & Search states
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [expandedCaseId, setExpandedCaseId] = useState<string | null>(null);

  useEffect(() => {
    loadEvalData();
  }, []);

  const loadEvalData = async () => {
    setLoading(true);
    setErrorMsg("");
    try {
      const data = await getEvalsData();
      if (data.error) {
        setErrorMsg(data.error);
        setEvalData(null);
      } else {
        setEvalData(data);
      }
    } catch (e: any) {
      setErrorMsg("Evaluation results not found. Trigger a run below to generate them.");
      setEvalData(null);
    } finally {
      setLoading(false);
    }
  };

  const handleRunSuite = async () => {
    setRunningSuite(true);
    setRunningMsg("Launching test suite in the background (140+ test cases)...");
    try {
      const res = await triggerEvalsRun();
      if (res.success) {
        setRunningMsg("TestSuite is currently executing. This will take about 1-2 minutes. Click Refresh periodically to pull results.");
        // Poll for results every 15s
        const interval = setInterval(async () => {
          try {
            const data = await getEvalsData();
            if (!data.error) {
              setEvalData(data);
              setRunningSuite(false);
              setRunningMsg("");
              clearInterval(interval);
            }
          } catch (err) {
            // keep polling
          }
        }, 15000);
      } else {
        setRunningMsg("Failed to launch evaluation suite.");
        setRunningSuite(false);
      }
    } catch (e: any) {
      setRunningMsg(`Error: ${e.message || "Failed to start suite"}`);
      setRunningSuite(false);
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedCaseId(prev => (prev === id ? null : id));
  };

  const getMetricColor = (val: number, type: "percentage" | "latency" | "hallucination") => {
    if (type === "latency") {
      return val < 1.5 ? "text-emerald-400" : val < 2.5 ? "text-amber-400" : "text-rose-500";
    }
    if (type === "hallucination") {
      return val < 0.05 ? "text-emerald-400" : val < 0.15 ? "text-amber-400" : "text-rose-500";
    }
    return val > 0.85 ? "text-emerald-400" : val > 0.7 ? "text-amber-400" : "text-rose-500";
  };

  // Filter test cases
  const filteredCases = evalData?.details?.filter(tc => {
    const matchesSearch = tc.question.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          tc.answer.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = selectedCategory === "all" || tc.category === selectedCategory;
    return matchesSearch && matchesCategory;
  }) || [];

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50 flex flex-col antialiased relative">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(168,85,247,0.06),transparent_50%),radial-gradient(ellipse_at_bottom_left,rgba(99,102,241,0.07),transparent_50%)] pointer-events-none" />

      {/* Header */}
      <header className="glass-panel sticky top-0 z-40 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/" className="glass-button p-2 text-zinc-400 rounded-lg hover:text-white transition">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-indigo-300 via-purple-200 to-indigo-100 bg-clip-text text-transparent">
              Evaluation & Guardrail Suite
            </h1>
            <p className="text-xs text-indigo-300/80 font-medium">Auto-Evaluation (LLM-as-a-judge) Metrics</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <button 
            onClick={loadEvalData} 
            disabled={loading}
            className="glass-button text-xs py-2 px-4 rounded-lg flex items-center gap-2 hover:text-white transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh Results
          </button>
        </div>
      </header>

      <div className="flex-1 max-w-7xl mx-auto w-full p-6 relative z-10 flex flex-col gap-6">
        
        {/* Error / Ingestion Prompt */}
        {!evalData && !loading && (
          <div className="glass-card rounded-2xl p-6 flex flex-col items-center justify-center text-center gap-4 max-w-xl mx-auto my-12">
            <AlertTriangle className="w-12 h-12 text-amber-500 animate-pulse" />
            <h3 className="text-lg font-bold text-zinc-200">No Evaluation Data Found</h3>
            <p className="text-sm text-zinc-400 leading-relaxed">
              Before viewing metrics, you must run the automatic evaluation suite. This suite tests 140+ cases across Resume QA, GitHub repositories, Scheduling, and Prompt Injection defenses.
            </p>
            <button
              onClick={handleRunSuite}
              disabled={runningSuite}
              className="glass-button-primary text-white py-3 px-6 rounded-xl text-sm font-semibold flex items-center gap-2 hover:opacity-95 disabled:opacity-50 transition"
            >
              <Play className="w-4 h-4 fill-white" />
              {runningSuite ? "Running Test Suite..." : "Run Evaluation Suite"}
            </button>
            {runningMsg && (
              <p className="text-xs text-indigo-300 bg-indigo-500/10 py-2 px-4 rounded-lg animate-pulse">{runningMsg}</p>
            )}
          </div>
        )}

        {/* Dashboard Grid */}
        {evalData && (
          <>
            {/* Top Stat Ring Cards */}
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              {/* Avg Latency */}
              <div className="glass-card rounded-2xl p-5 flex flex-col justify-between">
                <span className="text-xs font-semibold text-zinc-500 uppercase flex items-center gap-1.5"><Clock className="w-3.5 h-3.5 text-indigo-400" /> Avg Latency</span>
                <span className={`text-3xl font-bold mt-2 ${getMetricColor(evalData.metrics.avg_latency_sec, "latency")}`}>{evalData.metrics.avg_latency_sec}s</span>
                <span className="text-[10px] text-zinc-500 mt-1">Target threshold: &lt; 2s</span>
              </div>
              {/* Accuracy */}
              <div className="glass-card rounded-2xl p-5 flex flex-col justify-between">
                <span className="text-xs font-semibold text-zinc-500 uppercase flex items-center gap-1.5"><CheckCircle className="w-3.5 h-3.5 text-emerald-400" /> LLM Accuracy</span>
                <span className={`text-3xl font-bold mt-2 ${getMetricColor(evalData.metrics.avg_accuracy, "percentage")}`}>{Math.round(evalData.metrics.avg_accuracy * 100)}%</span>
                <span className="text-[10px] text-zinc-500 mt-1">Direct answering rate</span>
              </div>
              {/* Hallucination Rate */}
              <div className="glass-card rounded-2xl p-5 flex flex-col justify-between">
                <span className="text-xs font-semibold text-zinc-500 uppercase flex items-center gap-1.5"><AlertTriangle className="w-3.5 h-3.5 text-amber-500" /> Hallucination Rate</span>
                <span className={`text-3xl font-bold mt-2 ${getMetricColor(evalData.metrics.hallucination_rate, "hallucination")}`}>{Math.round(evalData.metrics.hallucination_rate * 100)}%</span>
                <span className="text-[10px] text-zinc-500 mt-1">Groundedness rate on missing facts</span>
              </div>
              {/* Prompt Injection Defense */}
              <div className="glass-card rounded-2xl p-5 flex flex-col justify-between">
                <span className="text-xs font-semibold text-zinc-500 uppercase flex items-center gap-1.5"><Shield className="w-3.5 h-3.5 text-purple-400" /> Jailbreak Defense</span>
                <span className={`text-3xl font-bold mt-2 ${getMetricColor(evalData.metrics.adversarial_defense_rate, "percentage")}`}>{Math.round(evalData.metrics.adversarial_defense_rate * 100)}%</span>
                <span className="text-[10px] text-zinc-500 mt-1">Percentage of injections blocked</span>
              </div>
              {/* Overall Success Rate */}
              <div className="glass-card rounded-2xl p-5 flex flex-col justify-between">
                <span className="text-xs font-semibold text-zinc-500 uppercase flex items-center gap-1.5"><Activity className="w-3.5 h-3.5 text-cyan-400" /> Total Test Runs</span>
                <span className="text-3xl font-bold mt-2 text-zinc-100">{evalData.successful_runs}/{evalData.total_tests}</span>
                <span className="text-[10px] text-zinc-500 mt-1">Passed test scenarios</span>
              </div>
            </div>

            {/* Run again card inside dashboard */}
            {runningMsg && (
              <div className="glass-card p-4 rounded-xl bg-indigo-950/20 border border-indigo-500/30 text-indigo-300 text-xs animate-pulse flex items-center justify-between">
                <span>{runningMsg}</span>
                <button onClick={loadEvalData} className="underline font-bold text-xs hover:text-white">Check Now</button>
              </div>
            )}

            {/* Category breakdown table */}
            <div className="glass-card rounded-2xl p-5">
              <h3 className="text-sm font-semibold text-zinc-400 mb-4 uppercase tracking-wide">Category Performance</h3>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {Object.entries(evalData.breakdown).map(([cat, info]: [string, any]) => (
                  <div key={cat} className="bg-zinc-900/40 border border-zinc-800/60 p-4 rounded-xl">
                    <h4 className="capitalize font-bold text-sm text-zinc-200 border-b border-zinc-800 pb-2 flex items-center justify-between">
                      {cat} QA
                      <span className="text-[10px] text-zinc-500">n={info.total}</span>
                    </h4>
                    <div className="flex flex-col gap-2 mt-3 text-xs">
                      <div className="flex justify-between text-zinc-400">
                        <span>Latency:</span>
                        <span className="font-semibold text-zinc-200">{info.avg_latency}s</span>
                      </div>
                      <div className="flex justify-between text-zinc-400">
                        <span>Accuracy:</span>
                        <span className="font-semibold text-zinc-200">{Math.round(info.avg_accuracy * 100)}%</span>
                      </div>
                      {cat !== "adversarial" ? (
                        <div className="flex justify-between text-zinc-400">
                          <span>Hallucination Rate:</span>
                          <span className="font-semibold text-zinc-200">{Math.round(info.hallucination_rate * 100)}%</span>
                        </div>
                      ) : (
                        <div className="flex justify-between text-zinc-400">
                          <span>Injections Blocked:</span>
                          <span className="font-semibold text-zinc-200">{info.defended_count}/{info.total}</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Test Case Explorer */}
            <div className="glass-card rounded-2xl p-5 flex flex-col gap-4">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800/80 pb-4">
                <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wide">Test Cases Explorer</h3>
                <div className="flex flex-wrap items-center gap-3">
                  {/* Category Filter */}
                  <div className="flex items-center gap-1.5 glass-input px-3 py-1.5 rounded-lg text-xs">
                    <Filter className="w-3.5 h-3.5 text-zinc-500" />
                    <select 
                      value={selectedCategory} 
                      onChange={(e) => setSelectedCategory(e.target.value)}
                      className="bg-transparent border-none text-zinc-300 outline-none text-xs"
                    >
                      <option value="all" className="bg-zinc-950 text-zinc-300">All Categories</option>
                      <option value="resume" className="bg-zinc-950 text-zinc-300">Resume</option>
                      <option value="github" className="bg-zinc-950 text-zinc-300">GitHub</option>
                      <option value="scheduling" className="bg-zinc-950 text-zinc-300">Scheduling</option>
                      <option value="adversarial" className="bg-zinc-950 text-zinc-300">Adversarial</option>
                    </select>
                  </div>
                  {/* Search Query */}
                  <div className="flex items-center gap-2 glass-input px-3 py-1.5 rounded-lg text-xs w-60">
                    <Search className="w-3.5 h-3.5 text-zinc-500" />
                    <input
                      type="text"
                      placeholder="Search questions or answers..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="bg-transparent border-none text-zinc-300 outline-none text-xs w-full"
                    />
                  </div>
                </div>
              </div>

              {/* Table or collapsible items */}
              <div className="flex flex-col gap-2 max-h-[500px] overflow-y-auto pr-1">
                {filteredCases.length === 0 ? (
                  <div className="text-zinc-500 text-xs py-8 text-center bg-zinc-900/10 border border-zinc-800 rounded-xl">
                    No matching test cases found.
                  </div>
                ) : (
                  filteredCases.map((tc) => (
                    <div 
                      key={tc.id} 
                      className={`border border-zinc-800/80 rounded-xl overflow-hidden transition ${
                        expandedCaseId === tc.id ? "bg-zinc-900/30 border-zinc-700/60" : "bg-zinc-900/10 hover:border-zinc-800"
                      }`}
                    >
                      {/* Accordion Trigger Header */}
                      <button
                        onClick={() => toggleExpand(tc.id)}
                        className="w-full flex items-center justify-between p-4 text-left text-xs text-zinc-300 hover:text-zinc-100"
                      >
                        <div className="flex items-center gap-3 w-5/6">
                          <span className="text-[10px] font-bold text-zinc-500 shrink-0">{tc.id}</span>
                          <span className={`px-2 py-0.5 rounded-md text-[9px] font-bold uppercase shrink-0 ${
                            tc.category === "adversarial" ? "bg-purple-500/10 text-purple-400 border border-purple-500/20" :
                            tc.category === "resume" ? "bg-blue-500/10 text-blue-400 border border-blue-500/20" :
                            tc.category === "github" ? "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20" :
                            "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20"
                          }`}>
                            {tc.category}
                          </span>
                          <span className="font-semibold truncate">{tc.question}</span>
                        </div>
                        <div className="flex items-center gap-4">
                          <span className="text-[10px] text-zinc-500">{tc.latency}s</span>
                          {expandedCaseId === tc.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        </div>
                      </button>

                      {/* Accordion Expandable Content */}
                      {expandedCaseId === tc.id && (
                        <div className="border-t border-zinc-800/80 p-4 bg-zinc-950/40 flex flex-col gap-3 text-xs leading-relaxed">
                          <div>
                            <span className="font-semibold text-zinc-400 block mb-1">Answered:</span>
                            <div className="bg-zinc-950/60 border border-zinc-800/60 p-3 rounded-lg text-zinc-300 whitespace-pre-line">
                              {tc.answer}
                            </div>
                          </div>
                          
                          {/* Scoring / evaluation tags */}
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 border-t border-zinc-900/60 pt-3">
                            <div>
                              <span className="text-[10px] text-zinc-500 block">Accuracy Score:</span>
                              <span className={`font-semibold ${getMetricColor(tc.accuracy, "percentage")}`}>{Math.round(tc.accuracy * 100)}%</span>
                            </div>
                            <div>
                              <span className="text-[10px] text-zinc-500 block">Hallucinated:</span>
                              {tc.category !== "adversarial" ? (
                                <span className={`font-semibold ${tc.hallucinated ? "text-rose-400" : "text-emerald-400"}`}>
                                  {tc.hallucinated ? "True" : "False (Grounded)"}
                                </span>
                              ) : (
                                <span className="text-zinc-500">N/A</span>
                              )}
                            </div>
                            <div>
                              <span className="text-[10px] text-zinc-500 block">Jailbreak Guard:</span>
                              {tc.category === "adversarial" ? (
                                <span className={`font-semibold ${tc.defended ? "text-emerald-400" : "text-rose-400"}`}>
                                  {tc.defended ? "Defended" : "Failed"}
                                </span>
                              ) : (
                                <span className="text-zinc-500">N/A</span>
                              )}
                            </div>
                            <div>
                              <span className="text-[10px] text-zinc-500 block">RAG Precision / Recall:</span>
                              {tc.category === "resume" || tc.category === "github" ? (
                                <span className="text-zinc-300 font-semibold">{tc.retrieval_precision} / {tc.retrieval_recall}</span>
                              ) : (
                                <span className="text-zinc-500">N/A</span>
                              )}
                            </div>
                          </div>

                          <div className="bg-zinc-900/30 border border-zinc-800/40 p-2.5 rounded-lg text-[10px] text-zinc-400">
                            <span className="font-semibold text-zinc-500 block mb-0.5">Judge Reason:</span>
                            {tc.reason}
                          </div>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Run again button at the bottom */}
            <div className="flex justify-end pt-4">
              <button
                onClick={handleRunSuite}
                disabled={runningSuite}
                className="glass-button-primary text-white py-3 px-6 rounded-xl text-xs font-semibold flex items-center gap-2 hover:opacity-95 disabled:opacity-50 transition"
              >
                <Play className="w-4 h-4 fill-white" />
                {runningSuite ? "Running Test Suite..." : "Trigger New Evaluation Run"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
