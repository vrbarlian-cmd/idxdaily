'use client';

/**
 * /admin/foreign-flow — read-only log view.
 *
 * Flow data is entered via CLI only:
 *   python -m backend.scripts.set_foreign_flow --value -1234.56
 *   python -m backend.scripts.set_domestic_flow --buy 6240 --sell 5180
 *
 * This page shows recent entries so you can verify data was saved correctly.
 * There is no form here — no writable endpoint is exposed publicly.
 */

import { useState, useEffect, useCallback } from 'react';

interface ForeignEntry {
  date: string;
  net_idr_billions: number;
}

interface DomesticEntry {
  date: string;
  buy_value_bn: number;
  sell_value_bn: number;
  net_idr_billions: number;
}

export default function FlowLogPage() {
  const [ffEntries, setFfEntries] = useState<ForeignEntry[]>([]);
  const [dfEntries, setDfEntries] = useState<DomesticEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ffRes, dfRes] = await Promise.all([
        fetch('/api/admin/foreign-flow').then(r => r.json()),
        fetch('/api/admin/domestic-flow').then(r => r.json()),
      ]);
      if (ffRes.ok) setFfEntries(ffRes.entries);
      if (dfRes.ok) setDfEntries(dfRes.entries);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="min-h-screen bg-stone-50">
      <main className="max-w-2xl mx-auto px-4 py-10 space-y-8">

        <div>
          <h1 className="text-2xl font-bold text-stone-900">Flow Log</h1>
          <p className="text-sm text-stone-500 mt-1">
            Data terbaru foreign &amp; domestic flow. Hanya baca — masukkan data lewat terminal.
          </p>
          <div className="mt-3 bg-stone-100 border border-stone-200 rounded-xl px-4 py-3 space-y-1 font-mono text-xs text-stone-600">
            <p className="font-semibold text-stone-500 mb-1.5">Perintah harian (jalankan dari project root):</p>
            <p className="text-stone-700">{'# Asing — net saja (minimal):'}</p>
            <p>python -m backend.scripts.set_foreign_flow --value -1234.56</p>
            <p className="text-stone-400 mt-1">{'# Asing — dengan total buy/sell untuk formula market-share (dianjurkan):'}</p>
            <p>python -m backend.scripts.set_foreign_flow --value -1234.56 --buy-total 3500 --sell-total 4734</p>
            <p className="text-stone-700 mt-2">{'# Domestik (wajib untuk Sentimen Ritel + Overall):'}</p>
            <p>python -m backend.scripts.set_domestic_flow --buy 6240 --sell 5180</p>
          </div>
          <p className="mt-2 text-xs text-stone-400">
            set_foreign_flow → Foreign Score + Overall Score.
            set_domestic_flow → Domestic Score + Overall Score.
            Kedua perintah memperbarui Overall secara otomatis.
          </p>
        </div>

        {loading ? (
          <p className="text-sm text-stone-400">Memuat...</p>
        ) : (
          <>
            {/* Foreign flow */}
            <section>
              <h2 className="text-sm font-semibold text-stone-700 uppercase tracking-widest mb-3">
                Foreign Flow — 10 Terakhir
              </h2>
              {ffEntries.length === 0 ? (
                <p className="text-sm text-stone-400">Belum ada data.</p>
              ) : (
                <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden shadow-sm">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-stone-50 border-b border-stone-100">
                        <th className="text-left px-4 py-2.5 text-xs font-medium text-stone-400 uppercase tracking-wider">Tanggal</th>
                        <th className="text-right px-4 py-2.5 text-xs font-medium text-stone-400 uppercase tracking-wider">Net (IDR Miliar)</th>
                        <th className="text-right px-4 py-2.5 text-xs font-medium text-stone-400 uppercase tracking-wider">Tipe</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stone-100">
                      {ffEntries.map(e => (
                        <tr key={e.date} className="hover:bg-stone-50">
                          <td className="px-4 py-2.5 font-mono text-stone-700">{e.date}</td>
                          <td className={`px-4 py-2.5 font-mono text-right font-semibold ${e.net_idr_billions >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                            {e.net_idr_billions >= 0 ? '+' : ''}{e.net_idr_billions.toFixed(2)}
                          </td>
                          <td className="px-4 py-2.5 text-right">
                            <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${e.net_idr_billions >= 0 ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-500'}`}>
                              {e.net_idr_billions >= 0 ? 'Net Buy' : 'Net Jual'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* Domestic flow */}
            <section>
              <h2 className="text-sm font-semibold text-stone-700 uppercase tracking-widest mb-3">
                Domestic Flow — 10 Terakhir
              </h2>
              {dfEntries.length === 0 ? (
                <p className="text-sm text-stone-400">Belum ada data domestic flow.</p>
              ) : (
                <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden shadow-sm">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-stone-50 border-b border-stone-100">
                        <th className="text-left px-4 py-2.5 text-xs font-medium text-stone-400 uppercase tracking-wider">Tanggal</th>
                        <th className="text-right px-4 py-2.5 text-xs font-medium text-stone-400 uppercase tracking-wider">Buy</th>
                        <th className="text-right px-4 py-2.5 text-xs font-medium text-stone-400 uppercase tracking-wider">Sell</th>
                        <th className="text-right px-4 py-2.5 text-xs font-medium text-stone-400 uppercase tracking-wider">Net</th>
                        <th className="text-right px-4 py-2.5 text-xs font-medium text-stone-400 uppercase tracking-wider">Tipe</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stone-100">
                      {dfEntries.map(e => (
                        <tr key={e.date} className="hover:bg-stone-50">
                          <td className="px-4 py-2.5 font-mono text-stone-700">{e.date}</td>
                          <td className="px-4 py-2.5 font-mono text-right text-stone-600">{e.buy_value_bn.toFixed(0)}</td>
                          <td className="px-4 py-2.5 font-mono text-right text-stone-600">{e.sell_value_bn.toFixed(0)}</td>
                          <td className={`px-4 py-2.5 font-mono text-right font-semibold ${e.net_idr_billions >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                            {e.net_idr_billions >= 0 ? '+' : ''}{e.net_idr_billions.toFixed(0)}
                          </td>
                          <td className="px-4 py-2.5 text-right">
                            <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${e.net_idr_billions >= 0 ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-500'}`}>
                              {e.net_idr_billions >= 0 ? 'Net Beli' : 'Net Jual'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        )}

        <button
          onClick={load}
          className="text-xs text-stone-400 hover:text-stone-600 transition-colors"
        >
          Refresh
        </button>
      </main>
    </div>
  );
}
