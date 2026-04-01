"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
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

export default function ChartsSection() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);

  if (!mounted) {
    return null;
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
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
        <div className="w-full">
          <ResponsiveContainer width="100%" height={300} minWidth={1}>
            <AreaChart data={cveData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="colorFixed" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#34d399" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#34d399" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorCritical" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#3c4868" vertical={false} />
              <XAxis dataKey="name" stroke="#7e91b5" tick={{ fill: "#7e91b5", fontSize: 12 }} axisLine={false} tickLine={false} />
              <YAxis stroke="#7e91b5" tick={{ fill: "#7e91b5", fontSize: 12 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ backgroundColor: "#1a1e2d", borderColor: "#3c4868", borderRadius: "8px" }}
                itemStyle={{ color: "#e9ebf3" }}
              />
              <Area type="monotone" dataKey="fixed" stroke="#34d399" strokeWidth={2} fillOpacity={1} fill="url(#colorFixed)" name="Auto-Fixed" />
              <Area type="monotone" dataKey="critical" stroke="#f43f5e" strokeWidth={2} fillOpacity={1} fill="url(#colorCritical)" name="Critical CVEs" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </motion.div>

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
        <div className="w-full">
          <ResponsiveContainer width="100%" height={260} minWidth={1}>
            <BarChart data={blockData} layout="vertical" margin={{ top: 0, right: 0, left: 10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#3c4868" horizontal={true} vertical={false} />
              <XAxis type="number" hide />
              <YAxis dataKey="name" type="category" stroke="#7e91b5" tick={{ fill: "#aab8d0", fontSize: 12 }} axisLine={false} tickLine={false} width={80} />
              <Tooltip
                cursor={{ fill: "#343d56", opacity: 0.4 }}
                contentStyle={{ backgroundColor: "#1a1e2d", borderColor: "#3c4868", borderRadius: "8px" }}
              />
              <Bar dataKey="value" fill="#f59e0b" radius={[0, 4, 4, 0]} barSize={24} name="Blocks" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </motion.div>
    </div>
  );
}
