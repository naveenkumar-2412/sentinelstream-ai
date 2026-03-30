"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
} from "recharts";
import { ShieldAlert, ShieldCheck, Activity, Clock, ServerCrash, ExternalLink } from "lucide-react";

// --- Mock Data ---
const cveData = [
  { name: "Mon", critical: 2, high: 5, fixed: 6 },
  { name: "Tue", critical: 1, high: 3, fixed: 4 },
  { name: "Wed", critical: 4, high: 7, fixed: 10 },
  { name: "Thu", critical: 0, high: 2, fixed: 2 },
  { name: "Fri", critical: 3, high: 4, fixed: 7 },
  { name: "Sat", critical: 1, high: 1, fixed: 2 },
  { name: "Sun", critical: 0, high: 1, fixed: 1 },
];

const blockData = [
  { name: "AGPL-3.0", value: 45 },
  { name: "GPL-2.0", value: 30 },
  { name: "GPL-3.0", value: 20 },
  { name: "SSPL-1.0", value: 5 },
];

const recentAudits = [
  { id: "!402", project: "core-auth", package: "express@3.1.0", status: "🔴 Blocked", time: "10m ago" },
  { id: "!401", project: "ui-kit", package: "react@18.2.0", status: "✅ Pass", time: "1h ago" },
  { id: "!400", project: "data-pipeline", package: "itextpdf@5.5.13", status: "🔴 Blocked", time: "2h ago" },
  { id: "!399", project: "payment-gw", package: "lodash@4.17.21", status: "✅ Pass", time: "4h ago" },
  { id: "!398", project: "core-auth", package: "jsonwebtoken@8.5.1", status: "🟠 Warn", time: "5h ago" },
];

export default function Dashboard() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-in fade-in duration-700 pb-20">
      
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white mb-2">Fleet Intelligence</h1>
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
        
        {/* Main Chart: CVEs vs Fixes */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.5 }}
          className="lg:col-span-2 glass-panel rounded-xl p-6"
        >
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-white">Vulnerability Remediation Velocity</h2>
            <p className="text-sm text-vulcan-400">Critical & High CVEs vs SentinelStream Auto-Fixes</p>
          </div>
          <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={cveData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorFixed" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#34d399" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#34d399" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorCritical" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#f43f5e" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#3c4868" vertical={false} />
                <XAxis dataKey="name" stroke="#7e91b5" tick={{ fill: '#7e91b5', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis stroke="#7e91b5" tick={{ fill: '#7e91b5', fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1a1e2d', borderColor: '#3c4868', borderRadius: '8px' }}
                  itemStyle={{ color: '#e9ebf3' }}
                />
                <Area type="monotone" dataKey="fixed" stroke="#34d399" strokeWidth={2} fillOpacity={1} fill="url(#colorFixed)" name="Auto-Fixed" />
                <Area type="monotone" dataKey="critical" stroke="#f43f5e" strokeWidth={2} fillOpacity={1} fill="url(#colorCritical)" name="Critical CVEs" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Top Blocked Licenses */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.6 }}
          className="glass-panel rounded-xl p-6 flex flex-col"
        >
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
               Policy Violations <span className="text-xs bg-vulcan-800 px-2 py-1 rounded text-vulcan-300">Licenses</span>
            </h2>
          </div>
          <div className="flex-1 min-h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={blockData} layout="vertical" margin={{ top: 0, right: 0, left: 10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#3c4868" horizontal={true} vertical={false} />
                <XAxis type="number" hide />
                <YAxis dataKey="name" type="category" stroke="#7e91b5" tick={{ fill: '#aab8d0', fontSize: 12 }} axisLine={false} tickLine={false} width={80} />
                <Tooltip 
                  cursor={{ fill: '#343d56', opacity: 0.4 }}
                  contentStyle={{ backgroundColor: '#1a1e2d', borderColor: '#3c4868', borderRadius: '8px' }}
                />
                <Bar dataKey="value" fill="#f59e0b" radius={[0, 4, 4, 0]} barSize={24} name="Blocks" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

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
                <tr key={i} className="hover:bg-vulcan-800/30 transition-colors group cursor-pointer">
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

    </div>
  );
}

// --- Components ---

function MetricCard({ title, value, trend, icon, color, delay, subtitle }: any) {
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
