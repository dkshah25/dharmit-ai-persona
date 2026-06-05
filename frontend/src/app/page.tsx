"use client";

import React, { useState, useEffect, useRef } from "react";
import { 
  Send, RefreshCw, ArrowRight, Settings, Check
} from "lucide-react";
import { 
  Message, Source, getBackendStatus, triggerIngestion, fetchSlots, bookSlot, streamChat 
} from "../lib/api";
import Link from "next/link";

export default function Home() {
  // Chat state
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Hello! I am Dharmit Shah's AI representative. You can ask me about his resume, GitHub projects, development tradeoffs, or book an interview with him. How can I help you today?" }
  ]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentSources, setCurrentSources] = useState<Source[]>([]);
  const [statusMessage, setStatusMessage] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Status & Ingestion state
  const [status, setStatus] = useState({
    openai_configured: false,
    github_configured: false,
    cal_configured: false,
    resume_uploaded: false,
    vector_db_built: false
  });
  const [ingesting, setIngesting] = useState(false);
  const [ingestMsg, setIngestMsg] = useState("");
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // Scheduler state
  const [slots, setSlots] = useState<string[]>([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);
  const [bookingForm, setBookingForm] = useState({ name: "", email: "", notes: "" });
  const [bookingLoading, setBookingLoading] = useState(false);
  const [bookingResult, setBookingResult] = useState<{ success: boolean; message: string; link?: string } | null>(null);

  // Auto-scroll chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming, statusMessage]);

  // Load Status and Slots on mount
  useEffect(() => {
    refreshStatus();
    loadSlots();
  }, []);

  const refreshStatus = async () => {
    try {
      const s = await getBackendStatus();
      setStatus(s);
    } catch (e) {
      console.error(e);
    }
  };

  const loadSlots = async () => {
    setLoadingSlots(true);
    try {
      const data = await fetchSlots();
      setSlots(data.slots || []);
    } catch (e) {
      console.error("Failed to load availability slots:", e);
    } finally {
      setLoadingSlots(false);
    }
  };

  const handleIngest = async () => {
    setIngesting(true);
    setIngestMsg("Syncing data pipeline...");
    try {
      const res = await triggerIngestion();
      if (res.success) {
        setIngestMsg(`Success! Ingested ${res.repositories_ingested} repositories and updated ChromaDB.`);
        refreshStatus();
      } else {
        setIngestMsg("Ingestion succeeded but vector database indexing failed.");
      }
    } catch (e: any) {
      setIngestMsg(`Error: ${e.message || "Failed to complete pipeline"}`);
    } finally {
      setIngesting(false);
    }
  };

  const handleSendMessage = async (textToSend?: string) => {
    const query = textToSend || input;
    if (!query.trim() || isStreaming) return;

    if (!textToSend) setInput("");
    
    const userMsg: Message = { role: "user", content: query };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setIsStreaming(true);
    setStatusMessage("");
    setCurrentSources([]);
    
    // Add empty placeholder assistant message
    setMessages(prev => [...prev, { role: "assistant", content: "" }]);

    try {
      await streamChat(
        updatedMessages,
        (chunk) => {
          if (chunk.error) {
            setMessages(prev => {
              const next = [...prev];
              const last = next[next.length - 1];
              next[next.length - 1] = {
                ...last,
                content: `Error: ${chunk.error}`
              };
              return next;
            });
            return;
          }
          
          if (chunk.sources) {
            setCurrentSources(chunk.sources);
          }
          
          if (chunk.status) {
            setStatusMessage(chunk.status);
          }

          if (chunk.choices && chunk.choices[0]?.delta?.content) {
            const txt = chunk.choices[0].delta.content;
            setMessages(prev => {
              const next = [...prev];
              const last = next[next.length - 1];
              next[next.length - 1] = {
                ...last,
                content: last.content + txt
              };
              return next;
            });
          }
        },
        () => {
          setIsStreaming(false);
          setStatusMessage("");
        }
      );
    } catch (err: any) {
      setMessages(prev => {
        const next = [...prev];
        const last = next[next.length - 1];
        next[next.length - 1] = {
          ...last,
          content: `Failed to get response: ${err.message || "Unknown error"}`
        };
        return next;
      });
      setIsStreaming(false);
      setStatusMessage("");
    }
  };

  const handleBookMeeting = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSlot) return;

    setBookingLoading(true);
    setBookingResult(null);

    try {
      const res = await bookSlot({
        start_time: selectedSlot,
        name: bookingForm.name,
        email: bookingForm.email,
        notes: bookingForm.notes
      });
      if (res.success) {
        setBookingResult({
          success: true,
          message: `Interview confirmed at ${formatDate(selectedSlot)}!`,
          link: res.cal_link
        });
        setBookingForm({ name: "", email: "", notes: "" });
        setSelectedSlot(null);
        loadSlots(); // reload slots
      } else {
        setBookingResult({
          success: false,
          message: res.error || "Booking failed"
        });
      }
    } catch (err: any) {
      setBookingResult({
        success: false,
        message: err.message || "Failed to register slot"
      });
    } finally {
      setBookingLoading(false);
    }
  };

  const formatDate = (isoStr: string) => {
    const d = new Date(isoStr);
    return d.toLocaleDateString("en-US", { 
      weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" 
    });
  };

  const suggestedQuestions = [
    "Why should we hire Dharmit?",
    "Tell me about ScholarMind",
    "Compare VisionAct and MarketMind",
    "What evidence shows Dharmit can build production AI systems?"
  ];

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-150 flex flex-col antialiased relative">
      {/* Soft background light spots */}
      <div className="absolute top-0 left-[20%] w-[650px] h-[650px] bg-purple-900/3 blur-[140px] rounded-full pointer-events-none" />
      <div className="absolute bottom-0 right-[20%] w-[650px] h-[650px] bg-indigo-900/3 blur-[140px] rounded-full pointer-events-none" />

      {/* Global Header */}
      <header className="px-12 py-7 flex items-center justify-between border-b border-zinc-900/40 bg-zinc-950/20 backdrop-blur-md sticky top-0 z-40">
        <div>
          <span className="text-sm font-bold tracking-tight text-white">Dharmit Shah AI</span>
          <span className="text-[10px] text-zinc-500 ml-2 font-medium tracking-wide uppercase">Representative</span>
        </div>
        <div className="flex items-center gap-8">
          <Link href="/evals" className="text-zinc-400 hover:text-white text-xs font-semibold transition">
            Evals
          </Link>
          <button 
            onClick={() => setIsSettingsOpen(true)}
            className="text-zinc-400 hover:text-white text-xs font-semibold transition cursor-pointer"
          >
            Diagnostics & Sync
          </button>
        </div>
      </header>

      {/* Typographic AI Page Grid */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-12 p-12 max-w-7xl mx-auto w-full relative z-10 overflow-hidden">
        
        {/* LEFT/CENTER AREA (Main Chat - 75% screen / col-span-9) */}
        <section className="lg:col-span-8 flex flex-col h-[calc(100vh-170px)] justify-between pr-4">
          
          {/* Messages list container */}
          <div className="flex-1 overflow-y-auto px-2 py-6 flex flex-col gap-10 scrollbar-none">
            {messages.length === 1 ? (
              // Claude-inspired minimal typography empty state
              <div className="max-w-2xl mx-auto w-full flex-1 flex flex-col justify-center py-8 animate-fade-in">
                <h1 className="text-3xl font-light tracking-tight text-white">Dharmit's AI Representative</h1>
                <p className="text-sm text-zinc-400 mt-3 mb-12 leading-relaxed">
                  An AI representative grounded on Dharmit Shah's resume, open-source work, commit logs, and engineering documentation. Ask about his skills, projects, architectural decisions, or book an interview.
                </p>

                {/* Recruiter Suggestions */}
                <div className="grid grid-cols-2 gap-4 w-full">
                  {suggestedQuestions.map((q, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSendMessage(q)}
                      className="text-left text-xs bg-zinc-900/10 hover:bg-zinc-900/30 border border-zinc-900/30 hover:border-zinc-800/80 p-5 rounded-2xl text-zinc-300 hover:text-white transition-all flex items-center justify-between group cursor-pointer"
                    >
                      <span className="truncate pr-2 font-medium leading-relaxed">{q}</span>
                      <ArrowRight className="w-3.5 h-3.5 text-zinc-700 group-hover:text-zinc-400 group-hover:translate-x-0.5 transition-all shrink-0" />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              // Chat conversation log
              <div className="max-w-2xl mx-auto w-full flex flex-col gap-10 py-4">
                {messages.map((msg, i) => (
                  <div
                    key={i}
                    className={`flex w-full ${
                      msg.role === "user" ? "justify-end" : ""
                    } animate-fade-in`}
                  >
                    <div className="flex flex-col gap-3 max-w-[85%]">
                      {msg.role === "user" ? (
                        <div className="bg-zinc-900/30 text-zinc-100 border border-zinc-900/50 px-5.5 py-4 rounded-2xl rounded-tr-none text-sm leading-relaxed">
                          {msg.content}
                        </div>
                      ) : (
                        <div className="text-zinc-200 leading-relaxed text-sm">
                          {msg.content === "" ? (
                            <div className="flex items-center gap-1.5 py-2">
                              <span className="w-1.5 h-1.5 bg-zinc-600 rounded-full animate-pulse" style={{ animationDelay: "0ms" }} />
                              <span className="w-1.5 h-1.5 bg-zinc-600 rounded-full animate-pulse" style={{ animationDelay: "150ms" }} />
                              <span className="w-1.5 h-1.5 bg-zinc-600 rounded-full animate-pulse" style={{ animationDelay: "300ms" }} />
                            </div>
                          ) : (
                            <span className="whitespace-pre-line">{msg.content}</span>
                          )}
                        </div>
                      )}

                      {/* Redesigned Minimal Grounded Source Badges */}
                      {msg.role === "assistant" && i === messages.length - 1 && currentSources.length > 0 && (
                        <div className="flex flex-wrap gap-2 items-center mt-3 animate-fade-in">
                          <span className="text-[9px] text-zinc-500 font-bold uppercase tracking-wider">
                            Sources:
                          </span>
                          {currentSources.map((source, sIdx) => {
                            const isGit = source.name.toLowerCase().startsWith("github");
                            const displayName = isGit ? source.name.replace("GitHub: ", "") : source.name;
                            
                            return (
                              <div 
                                key={sIdx} 
                                className="text-[10px] px-2.5 py-0.5 rounded-md bg-zinc-900/40 border border-zinc-900 text-zinc-400 hover:text-white transition-all flex items-center gap-1"
                              >
                                <span className="font-medium">{displayName}</span>
                                {source.url && (
                                  <a href={source.url} target="_blank" rel="noreferrer" className="text-zinc-600 hover:text-zinc-400 transition shrink-0 ml-0.5 font-bold">
                                    →
                                  </a>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
            
            {statusMessage && (
              <div className="text-[10px] text-zinc-400 bg-zinc-900/40 border border-zinc-900/80 py-2.5 px-4.5 rounded-xl w-fit mx-auto flex items-center gap-2 animate-pulse">
                <span className="w-1.5 h-1.5 bg-violet-400 rounded-full shrink-0 animate-pulse" />
                <span>{statusMessage}</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Floating Typographic Input Area */}
          <div className="p-4 border-t border-zinc-900/40 bg-zinc-950/20 backdrop-blur-md flex items-center">
            <div className="max-w-2xl w-full mx-auto relative flex items-center">
              <input
                type="text"
                placeholder="Ask about projects, architecture, experience, GitHub repositories, or scheduling..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                disabled={isStreaming}
                className="w-full bg-zinc-900/20 border border-zinc-900/60 focus:border-zinc-800/80 rounded-2xl py-3.5 pl-6 pr-12 text-sm placeholder-zinc-500 text-zinc-200 focus:outline-none transition-all"
              />
              <button
                onClick={() => handleSendMessage()}
                disabled={isStreaming || !input.trim()}
                className="absolute right-3.5 p-2 rounded-xl text-zinc-500 hover:text-zinc-200 disabled:opacity-20 disabled:pointer-events-none transition cursor-pointer"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>

        </section>

        {/* RIGHT PANEL (Sleek Interview Scheduler - 25% screen / col-span-4) */}
        <aside className="lg:col-span-4 flex flex-col gap-8 pl-8 border-l border-zinc-900/40 pr-2">
          <div className="flex flex-col gap-6 h-[calc(100vh-170px)] overflow-y-auto pr-1">
            
            <div className="border-b border-zinc-900/30 pb-4">
              <h2 className="text-zinc-400 text-[10px] uppercase font-bold tracking-widest">
                Interview Scheduler
              </h2>
              <p className="text-xs text-zinc-500 mt-2 leading-relaxed">
                Select a date and time directly synced with Dharmit's active calendar.
              </p>
              
              {/* Simple text indicator */}
              <div className="flex items-center gap-1.5 mt-4 text-[10px] text-emerald-500 font-semibold uppercase tracking-wider">
                <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full shrink-0 animate-pulse" />
                <span>Real-time availability</span>
              </div>
            </div>

            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Available Slots</span>
                <button onClick={loadSlots} disabled={loadingSlots} className="text-zinc-500 hover:text-zinc-300 disabled:opacity-50 transition cursor-pointer">
                  <RefreshCw className={`w-3 h-3 ${loadingSlots ? "animate-spin" : ""}`} />
                </button>
              </div>

              {loadingSlots ? (
                <div className="text-xs text-zinc-500 py-10 text-center animate-pulse flex flex-col items-center gap-2">
                  Checking slots...
                </div>
              ) : slots.length === 0 ? (
                <div className="text-xs text-zinc-500 py-10 text-center bg-zinc-900/10 rounded-2xl border border-dashed border-zinc-900">
                  No slots currently available.
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-2.5 max-h-[300px] overflow-y-auto pr-1">
                  {slots.map((slot) => (
                    <button
                      key={slot}
                      onClick={() => {
                        setSelectedSlot(slot);
                        setBookingResult(null);
                      }}
                      className={`text-left text-xs py-3.5 px-4 rounded-xl border transition-all flex items-center justify-between group cursor-pointer ${
                        selectedSlot === slot 
                          ? "bg-zinc-900/50 border-zinc-700 text-white font-medium shadow-sm" 
                          : "bg-transparent border-zinc-900 text-zinc-400 hover:border-zinc-800 hover:text-zinc-200"
                      }`}
                    >
                      <span>{formatDate(slot)}</span>
                      <Check className={`w-3.5 h-3.5 text-zinc-400 transition-opacity ${selectedSlot === slot ? "opacity-100" : "opacity-0"}`} />
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Selected slot Booking Form */}
            {selectedSlot && (
              <form onSubmit={handleBookMeeting} className="flex flex-col gap-4 animate-fade-in mt-2 border-t border-zinc-900/30 pt-4">
                <div className="bg-zinc-900/20 border border-zinc-900 p-3.5 rounded-2xl text-[10px] text-zinc-350 leading-relaxed">
                  Interview Slot: <span className="font-semibold text-white block mt-0.5">{formatDate(selectedSlot)}</span>
                </div>
                <div className="flex flex-col gap-1">
                  <label className="block text-[10px] text-zinc-500 font-semibold mb-1 uppercase tracking-wider pl-1">Your Name</label>
                  <input
                    type="text"
                    required
                    value={bookingForm.name}
                    onChange={(e) => setBookingForm({...bookingForm, name: e.target.value})}
                    placeholder="Recruiter Name"
                    className="w-full glass-input text-xs py-2.5 px-4 rounded-xl"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="block text-[10px] text-zinc-500 font-semibold mb-1 uppercase tracking-wider pl-1">Your Email</label>
                  <input
                    type="email"
                    required
                    value={bookingForm.email}
                    onChange={(e) => setBookingForm({...bookingForm, email: e.target.value})}
                    placeholder="recruiter@company.com"
                    className="w-full glass-input text-xs py-2.5 px-4 rounded-xl"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="block text-[10px] text-zinc-500 font-semibold mb-1 uppercase tracking-wider pl-1">Notes (Optional)</label>
                  <textarea
                    rows={2}
                    value={bookingForm.notes}
                    onChange={(e) => setBookingForm({...bookingForm, notes: e.target.value})}
                    placeholder="Brief details..."
                    className="w-full glass-input text-xs py-2.5 px-4 rounded-xl resize-none"
                  />
                </div>
                <div className="flex gap-2.5 pt-1">
                  <button
                    type="button"
                    onClick={() => setSelectedSlot(null)}
                    className="flex-1 glass-button text-xs py-2.5 text-zinc-400 rounded-xl cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={bookingLoading}
                    className="flex-1 glass-button-primary text-xs py-2.5 text-white font-semibold rounded-xl disabled:opacity-50 cursor-pointer"
                  >
                    {bookingLoading ? "Booking..." : "Confirm Slot"}
                  </button>
                </div>
              </form>
            )}

            {/* Booking confirmation feedback */}
            {bookingResult && (
              <div className={`p-4 rounded-xl border flex flex-col gap-2 animate-fade-in ${
                bookingResult.success 
                  ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300" 
                  : "bg-rose-500/10 border-rose-500/20 text-rose-300"
              }`}>
                <div className="flex items-start gap-2">
                  <span className="text-xs font-semibold leading-relaxed">{bookingResult.message}</span>
                </div>
                {bookingResult.success && bookingResult.link && (
                  <a 
                    href={bookingResult.link} 
                    target="_blank" 
                    rel="noreferrer" 
                    className="text-[10px] text-emerald-400 underline hover:text-emerald-300 flex items-center gap-1 font-semibold mt-1"
                  >
                    View in Calendar
                  </a>
                )}
              </div>
            )}
          </div>
        </aside>

      </div>

      {/* DIAGNOSTICS & SYNC SIDE SETTINGS DRAWER OVERLAY */}
      {isSettingsOpen && (
        <div className="fixed inset-0 z-50 flex justify-end">
          {/* Backdrop overlay */}
          <div 
            className="absolute inset-0 bg-black/75 backdrop-blur-xs transition-opacity cursor-pointer animate-fade-in"
            onClick={() => setIsSettingsOpen(false)}
          />
          {/* Settings Drawer Panel */}
          <div className="relative w-full max-w-sm h-full bg-zinc-950/95 backdrop-blur-md border-l border-zinc-900/60 p-8 flex flex-col gap-8 shadow-2xl z-10 overflow-y-auto animate-fade-in">
            <div className="flex items-center justify-between border-b border-zinc-900 pb-4">
              <h2 className="text-md font-bold text-white flex items-center gap-2">
                <Settings className="w-4 h-4 text-violet-400" />
                Diagnostics & Sync
              </h2>
              <button 
                onClick={() => setIsSettingsOpen(false)}
                className="text-zinc-500 hover:text-zinc-300 text-xs font-semibold cursor-pointer"
              >
                Close
              </button>
            </div>
            
            {/* System Health Section */}
            <div className="flex flex-col gap-4">
              <h3 className="text-[10px] text-zinc-500 uppercase font-bold tracking-widest">
                System Health
              </h3>
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between text-xs bg-zinc-900/40 border border-zinc-900 p-3 rounded-2xl">
                  <span className="text-zinc-300 font-medium">Resume Indexed</span>
                  <span className={`w-2 h-2 rounded-full ${status.resume_uploaded && status.vector_db_built ? "bg-emerald-400 glow-indicator-green" : "bg-amber-400"}`} />
                </div>
                <div className="flex items-center justify-between text-xs bg-zinc-900/40 border border-zinc-900 p-3 rounded-2xl">
                  <span className="text-zinc-300 font-medium">GitHub Synced</span>
                  <span className={`w-2 h-2 rounded-full ${status.github_configured ? "bg-emerald-400 glow-indicator-green" : "bg-amber-400"}`} />
                </div>
                <div className="flex items-center justify-between text-xs bg-zinc-900/40 border border-zinc-900 p-3 rounded-2xl">
                  <span className="text-zinc-300 font-medium">Vector Store Ready</span>
                  <span className={`w-2 h-2 rounded-full ${status.vector_db_built ? "bg-emerald-400 glow-indicator-green" : "bg-amber-400"}`} />
                </div>
                <div className="flex items-center justify-between text-xs bg-zinc-900/40 border border-zinc-900 p-3 rounded-2xl">
                  <span className="text-zinc-300 font-medium">Calendar Connected</span>
                  <span className={`w-2 h-2 rounded-full ${status.cal_configured ? "bg-emerald-400 glow-indicator-green" : "bg-zinc-600"}`} />
                </div>
              </div>
            </div>

            {/* Ingestion Sync controls */}
            <div className="flex flex-col gap-3">
              <h3 className="text-[10px] text-zinc-500 uppercase font-bold tracking-widest">Controls</h3>
              <button 
                onClick={handleIngest} 
                disabled={ingesting}
                className="glass-button-primary text-xs py-3 px-4 rounded-xl flex items-center justify-center gap-2 text-white font-semibold hover:opacity-95 disabled:opacity-50 cursor-pointer"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${ingesting ? "animate-spin" : ""}`} />
                {ingesting ? "Syncing..." : "Sync Resume & GitHub"}
              </button>
              {ingestMsg && (
                <div className="text-[10px] bg-zinc-900/60 p-3 border border-zinc-800/60 rounded-xl text-zinc-300 whitespace-pre-line leading-relaxed">
                  {ingestMsg}
                </div>
              )}
            </div>

            {/* Quick Stats Section */}
            <div className="flex flex-col gap-4">
              <h3 className="text-[10px] text-zinc-500 uppercase font-bold tracking-widest">
                Platform Stats
              </h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-zinc-900/40 border border-zinc-900 p-3.5 rounded-2xl flex flex-col gap-1">
                  <span className="text-[9px] text-zinc-500 uppercase font-semibold">Repositories</span>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="text-xs font-bold text-white">GitHub: {status.vector_db_built ? "21+" : "0"}</span>
                  </div>
                </div>
                <div className="bg-zinc-900/40 border border-zinc-900 p-3.5 rounded-2xl flex flex-col gap-1">
                  <span className="text-[9px] text-zinc-500 uppercase font-semibold">Docs Loaded</span>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="text-xs font-bold text-white truncate">{status.resume_uploaded ? "Resume" : "None"}</span>
                  </div>
                </div>
                <div className="bg-zinc-900/40 border border-zinc-900 p-3.5 rounded-2xl flex flex-col gap-1">
                  <span className="text-[9px] text-zinc-500 uppercase font-semibold">Last Sync</span>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="text-[10px] font-bold text-white">{status.vector_db_built ? "Recent" : "Never"}</span>
                  </div>
                </div>
                <div className="bg-zinc-900/40 border border-zinc-900 p-3.5 rounded-2xl flex flex-col gap-1">
                  <span className="text-[9px] text-zinc-500 uppercase font-semibold">Latency</span>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="text-sm font-bold text-white">&lt; 180ms</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
