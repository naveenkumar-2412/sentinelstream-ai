"use client";

import { type ReactNode, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import { ShieldAlert, ShieldCheck, Activity, Clock, ExternalLink } from "lucide-react";

const ChartsSection = dynamic(() => import("./ChartsSection"), { ssr: false });

type AuditRow = {
  id: string;
  project: string;
  package: string;
  status: string;
  time: string;
};

type AuditReport = {
  mr_iid?: number;
  project_url?: string;
  blockers?: number;
  warnings?: number;
  total_scanned?: number;
  audits?: Array<{
    delta?: { new?: { name?: string; version?: string }; old?: { name?: string; version?: string } };
    remediation?: { recommended_version?: string };
  }>;
  reasoning_log?: string;
};

const fallbackAudits: AuditRow[] = [
  { id: "!402", project: "core-auth", package: "express@3.1.0", status: "🔴 Blocked", time: "10m ago" },
  { id: "!401", project: "ui-kit", package: "react@18.2.0", status: "✅ Pass", time: "1h ago" },
  { id: "!400", project: "data-pipeline", package: "itextpdf@5.5.13", status: "🔴 Blocked", time: "2h ago" },
  { id: "!399", project: "payment-gw", package: "lodash@4.17.21", status: "✅ Pass", time: "4h ago" },
  { id: "!398", project: "core-auth", package: "jsonwebtoken@8.5.1", status: "🟠 Warn", time: "5h ago" },
];

export default function Dashboard() {
  const [recentAudits, setRecentAudits] = useState<AuditRow[]>(fallbackAudits);
  const [auditReports, setAuditReports] = useState<AuditReport[]>([]);
  const [selectedAudit, setSelectedAudit] = useState<AuditReport | null>(null);
  const [statusInfo, setStatusInfo] = useState<{ uptime: string; lastAudit: string } | null>(null);
  const [policyInfo, setPolicyInfo] = useState<{ source: string; allowed: string[] } | null>(null);
  const apiBase = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8080";

  useEffect(() => {
    let isMounted = true;
    const loadAudits = async () => {
      try {
        const response = await fetch(`${apiBase}/audits?limit=10`);
        if (!response.ok) {
          return;
        }
        const payload = await response.json();
        const reports: AuditReport[] = payload.reports || [];
        const rows: AuditRow[] = reports.map((reportObj) => {
          const audit = reportObj.audits?.[0];
          const delta = audit?.delta?.new || audit?.delta?.old;
          const pkgName = delta?.name ? `${delta.name}@${delta.version || ""}` : "unknown";
          const status = reportObj.blockers && reportObj.blockers > 0
            ? "🔴 Blocked"
            : reportObj.warnings && reportObj.warnings > 0
              ? "🟠 Warn"
              : "✅ Pass";
          return {
            id: `!${reportObj.mr_iid ?? 0}`,
            project: reportObj.project_url ? reportObj.project_url.split("/").pop() || "project" : "project",
            package: pkgName,
            status,
            time: "just now",
          };
        });
        if (rows.length && isMounted) {
          setRecentAudits(rows);
          setAuditReports(reports);
          setSelectedAudit(reports[0] || null);
        }
      } catch {
        // fallback stays in place
      }
    };
    const loadStatus = async () => {
      try {
        const response = await fetch(`${apiBase}/status`);
        if (!response.ok) {
          return;
        }
        const payload = await response.json();
        const uptimeSeconds = payload.uptime_seconds || 0;
        const uptime = `${Math.floor(uptimeSeconds / 60)}m`;
        const lastAudit = payload.last_audit?.mr_iid ? `!${payload.last_audit.mr_iid}` : "none";
        if (isMounted) {
          setStatusInfo({ uptime, lastAudit });
        }
      } catch {
        // ignore
      }
    };
    const loadPolicy = async () => {
      try {
        const response = await fetch(`${apiBase}/policy`);
        if (!response.ok) {
          return;
        }
        const payload = await response.json();
        if (isMounted) {
          setPolicyInfo({
            source: payload.source || "default",
            allowed: payload.allowed_licenses || [],
          });
        }
      } catch {
        // ignore
      }
    };
    loadAudits();
    loadStatus();
    loadPolicy();
    return () => {
      isMounted = false;
    };
  }, [apiBase]);
  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-in fade-in duration-700 pb-20">
      
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <SentinelBadge score={98} />
            <h1 className="text-3xl font-bold tracking-tight text-white">Fleet Intelligence</h1>
          </div>
          <p className="text-vulcan-300">Live SentinelStream telemetry and dependency governance metrics.</p>
        </div>
        <div className="flex gap-2">
          <button className="px-4 py-2 rounded-md bg-vulcan-800 border border-vulcan-700 text-sm font-medium hover:bg-vulcan-700 transition">
            Export Report
          </button>
          <button className="px-4 py-2 rounded-md bg-emerald-500/20 border border-emerald-500/50 text-emerald-400 text-sm font-medium hover:bg-emerald-500/30 transition shadow-[0_0_15px_rgba(52,211,153,0.2)]">
            Run Manual Audit
          </button>
        </div>
      </div>

      {/* Top Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard 
          title="Governance Score" 
          value="98.2%" 
          trend="+1.2%" 
          icon={<ShieldCheck className="w-5 h-5 text-emerald-400" />} 
          color="emerald"
          delay={0.1}
        />
        <MetricCard 
          title="Avg Remediation Time" 
          value="3.2s" 
          trend="-99.9%" 
          icon={<Clock className="w-5 h-5 text-blue-400" />} 
          color="blue"
          delay={0.2}
          subtitle="Down from 3 days"
        />
        <MetricCard 
          title="Active Blockers" 
          value="12" 
          trend="-4" 
          icon={<ShieldAlert className="w-5 h-5 text-rose-500" />} 
          color="rose"
          delay={0.3}
          subtitle="Pending MR review"
        />
        <MetricCard 
          title="Auto-Merged Fixes" 
          value="143" 
          trend="+28" 
          icon={<Activity className="w-5 h-5 text-amber-500" />} 
          color="amber"
          delay={0.4}
        />
      </div>

      <ChartsSection />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="glass-panel rounded-xl p-6">
          <h2 className="text-lg font-semibold text-white mb-2">Service Status</h2>
          <div className="text-sm text-vulcan-300">
            <div>Uptime: <span className="text-vulcan-100">{statusInfo?.uptime || "--"}</span></div>
            <div>Last Audit: <span className="text-vulcan-100">{statusInfo?.lastAudit || "--"}</span></div>
          </div>
        </div>
        <div className="glass-panel rounded-xl p-6 lg:col-span-2">
          <h2 className="text-lg font-semibold text-white mb-2">Policy Snapshot</h2>
          <div className="text-xs text-vulcan-400 mb-2">Source: {policyInfo?.source || "default"}</div>
          <div className="flex flex-wrap gap-2">
            {(policyInfo?.allowed || ["MIT", "Apache-2.0", "BSD-3-Clause"]).map((license) => (
              <span key={license} className="text-xs px-2 py-1 rounded bg-vulcan-800 text-vulcan-200">
                {license}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Audits Table */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.7 }}
        className="glass-panel rounded-xl overflow-hidden mt-6"
      >
        <div className="p-6 border-b border-vulcan-800 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-white">Live MR Audits</h2>
           <div className="flex items-center gap-2 px-3 py-1 bg-emerald-500/10 rounded-full border border-emerald-500/20">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span className="text-xs text-emerald-400 font-medium tracking-wide text-uppercase">Listening to Webhooks</span>
           </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-vulcan-900/50">
                <th className="py-3 px-6 text-xs font-medium text-vulcan-400 uppercase tracking-wider">MR</th>
                <th className="py-3 px-6 text-xs font-medium text-vulcan-400 uppercase tracking-wider">Project</th>
                <th className="py-3 px-6 text-xs font-medium text-vulcan-400 uppercase tracking-wider">Dependency</th>
                <th className="py-3 px-6 text-xs font-medium text-vulcan-400 uppercase tracking-wider">Result</th>
                <th className="py-3 px-6 text-xs font-medium text-vulcan-400 uppercase tracking-wider text-right">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-vulcan-800">
              {recentAudits.map((audit, i) => (
                <tr
                  key={i}
                  className="hover:bg-vulcan-800/30 transition-colors group cursor-pointer"
                  onClick={() => setSelectedAudit(auditReports[i] || null)}
                >
                  <td className="py-4 px-6 text-sm flex items-center gap-2">
                    <a href="#" className="font-semibold text-blue-400 group-hover:text-blue-300 flex items-center gap-1">
                      {audit.id} <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </a>
                  </td>
                  <td className="py-4 px-6 text-sm text-vulcan-200">{audit.project}</td>
                  <td className="py-4 px-6 text-sm font-mono text-vulcan-300 bg-vulcan-900/40 rounded px-2 w-max inline-block mt-2 ml-4">
                    {audit.package}
                  </td>
                  <td className="py-4 px-6 text-sm font-medium">
                     {audit.status}
                  </td>
                  <td className="py-4 px-6 text-sm text-vulcan-400 text-right">{audit.time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>

      <div className="glass-panel rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-2">Audit Details</h2>
        {selectedAudit ? (
          <div className="text-sm text-vulcan-300 space-y-2">
            <div>MR: <span className="text-vulcan-100">!{selectedAudit.mr_iid ?? "--"}</span></div>
            <div>Project: <span className="text-vulcan-100">{selectedAudit.project_url || "--"}</span></div>
            <div>Scanned: <span className="text-vulcan-100">{selectedAudit.total_scanned ?? 0}</span></div>
            <div>Blockers: <span className="text-vulcan-100">{selectedAudit.blockers ?? 0}</span></div>
            <div>Warnings: <span className="text-vulcan-100">{selectedAudit.warnings ?? 0}</span></div>
            <div>
              Suggested Fix: <span className="text-vulcan-100">
                {selectedAudit.audits?.[0]?.remediation?.recommended_version || "none"}
              </span>
            </div>
          </div>
        ) : (
          <div className="text-sm text-vulcan-400">Select a row to see details.</div>
        )}
      </div>

    </div>
  );
}

// --- Components ---

type MetricCardProps = {
  title: string;
  value: string;
  trend: string;
  icon: ReactNode;
  color: "emerald" | "blue" | "rose" | "amber";
  delay: number;
  subtitle?: string;
};

function MetricCard({ title, value, trend, icon, color, delay, subtitle }: MetricCardProps) {
  const isPositive = trend.startsWith("+");
  const isNegative = trend.startsWith("-");
  
  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, delay }}
      className="glass-panel p-6 rounded-xl relative overflow-hidden group"
    >
      <div className={`absolute top-0 right-0 w-32 h-32 bg-${color}-500/5 rounded-full blur-[40px] -mr-10 -mt-10 transition-opacity group-hover:bg-${color}-500/10`} />
      
      <div className="flex justify-between items-start mb-4 relative z-10">
        <h3 className="text-sm font-medium text-vulcan-300">{title}</h3>
        <div className={`p-2 rounded-lg bg-${color}-500/10 border border-${color}-500/20`}>
          {icon}
        </div>
      </div>
      
      <div className="relative z-10 font-mono">
        <span className="text-3xl font-bold tracking-tight text-white glow-text">{value}</span>
      </div>
      
      <div className="mt-2 flex items-center gap-2 relative z-10">
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
          isPositive ? 'bg-emerald-500/20 text-emerald-400' : 
          isNegative ? 'bg-emerald-500/20 text-emerald-400' : 'bg-vulcan-700 text-vulcan-300'
        }`}>
          {trend}
        </span>
        {subtitle && <span className="text-xs text-vulcan-400">{subtitle}</span>}
      </div>
    </motion.div>
  );
}

type SentinelBadgeProps = {
  score: number;
};

function SentinelBadge({ score }: SentinelBadgeProps) {
  const clamped = Math.max(0, Math.min(100, score));
  const ring = 2 * Math.PI * 22;
  const offset = ring - (clamped / 100) * ring;
  return (
    <div className="flex items-center gap-3 px-3 py-2 rounded-full bg-vulcan-900/60 border border-emerald-500/30">
      <svg width="40" height="40" viewBox="0 0 48 48" className="text-emerald-400">
        <circle cx="24" cy="24" r="22" stroke="currentColor" strokeOpacity="0.2" strokeWidth="4" fill="none" />
        <circle
          cx="24"
          cy="24"
          r="22"
          stroke="currentColor"
          strokeWidth="4"
          fill="none"
          strokeDasharray={ring}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 24 24)"
        />
        <path
          d="M24 13l8 4v6c0 6-5.3 10.3-8 11-2.7-.7-8-5-8-11v-6l8-4z"
          fill="currentColor"
          opacity="0.2"
        />
        <path
          d="M24 16l6 3v4c0 4.5-4.1 8-6 8.5-1.9-.5-6-4-6-8.5v-4l6-3z"
          fill="currentColor"
          opacity="0.6"
        />
      </svg>
      <div className="leading-tight">
        <div className="text-xs uppercase tracking-wide text-vulcan-400">Sentinel Badge</div>
        <div className="text-sm font-semibold text-emerald-300">Governance {clamped}%</div>
      </div>
    </div>
  );
}
