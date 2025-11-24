"use client";

import { useEffect, useState } from "react";

type Job = {
  id: string;
  repo_url: string;
  repo_type: string;
  status: string;
  progress?: string | null;
  error?: string | null;
  created_at: number;
  updated_at: number;
  metadata?: Record<string, unknown>;
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () =>
    fetch("/api/jobs", { cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(await res.text());
        }
        return res.json();
      })
      .then((data) => {
        setJobs(Array.isArray(data) ? data : []);
        setError(null);
      })
      .catch((err) => setError(err.message));

  useEffect(() => {
    setLoading(true);
    refresh().finally(() => setLoading(false));
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-semibold mb-4">Wiki Jobs</h1>
      <p className="text-sm text-gray-400 mb-4">Background tasks for cloning/embedding repos. Updates every 5s.</p>
      {loading && <div className="text-sm">Loading…</div>}
      {error && <div className="text-sm text-red-500">{error}</div>}
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm border border-gray-700">
          <thead className="bg-gray-900">
            <tr>
              <th className="px-3 py-2 text-left">Repo</th>
              <th className="px-3 py-2 text-left">Status</th>
              <th className="px-3 py-2 text-left">Progress</th>
              <th className="px-3 py-2 text-left">Updated</th>
              <th className="px-3 py-2 text-left">Provider/Model</th>
              <th className="px-3 py-2 text-left">Error</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => {
              const meta = job.metadata as Record<string, unknown> | undefined;
              const provider = typeof meta?.provider === 'string' ? meta.provider : '';
              const model = typeof meta?.model === 'string' ? meta.model : '';
              const updated = new Date(job.updated_at * 1000).toLocaleTimeString();
              return (
                <tr key={job.id} className="border-t border-gray-800">
                  <td className="px-3 py-2">
                    <div className="font-mono text-xs break-all">{job.repo_url}</div>
                    <div className="text-gray-400 text-xs">{job.repo_type}</div>
                  </td>
                  <td className="px-3 py-2 capitalize">{job.status}</td>
                  <td className="px-3 py-2">{job.progress || ""}</td>
                  <td className="px-3 py-2">{updated}</td>
                  <td className="px-3 py-2 text-xs">
                    {provider}{model ? ` / ${model}` : ''}
                  </td>
                  <td className="px-3 py-2 text-red-400 text-xs">{job.error || ""}</td>
                </tr>
              );
            })}
            {jobs.length === 0 && !loading && (
              <tr>
                <td className="px-3 py-4 text-center text-gray-400" colSpan={6}>
                  No jobs yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
