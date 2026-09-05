import React, { useEffect, useState } from 'react';
import { fetchHealth, fetchRecoveries, fetchRecoveryDetail, fetchDemos, runDemoScenario } from './api';
import { Activity, ShieldAlert, ShieldCheck, Play, ArrowRight, Server, Box, CheckCircle2, XCircle, AlertCircle, Clock } from 'lucide-react';
import clsx from 'clsx';

function StatusBadge({ status, type }: { status: string; type?: 'execution' | 'policy' | 'verification' }) {
  if (!status) return null;
  const s = status.toLowerCase();
  let color = 'bg-border text-muted';
  
  if (type === 'policy') {
    color = s === 'true' || s === 'allowed' ? 'bg-success/10 text-success border-success/20' : 'bg-danger/10 text-danger border-danger/20';
  } else if (type === 'execution') {
    if (s === 'executed') color = 'bg-primary/10 text-primary border-primary/20';
    if (s === 'blocked') color = 'bg-danger/10 text-danger border-danger/20';
    if (s === 'scheduled') color = 'bg-warning/10 text-warning border-warning/20';
    if (s === 'stopped') color = 'bg-muted/10 text-muted border-border';
  } else if (type === 'verification') {
    if (s === 'recovered') color = 'bg-success/10 text-success border-success/20';
    if (s === 'pending') color = 'bg-warning/10 text-warning border-warning/20';
    if (s === 'failed' || s === 'not_recovered') color = 'bg-danger/10 text-danger border-danger/20';
  }

  return (
    <span className={clsx('px-2 py-0.5 text-xs rounded border', color)}>
      {status.toUpperCase()}
    </span>
  );
}

export default function App() {
  const [health, setHealth] = useState<any>(null);
  const [recoveries, setRecoveries] = useState<any[]>([]);
  const [selectedRecord, setSelectedRecord] = useState<any>(null);
  const [demos, setDemos] = useState<any>({});
  const [loadingDemo, setLoadingDemo] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const [h, recs, ds] = await Promise.all([
        fetchHealth(),
        fetchRecoveries(),
        fetchDemos()
      ]);
      setHealth(h);
      setRecoveries(recs);
      setDemos(ds);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSelectRecord = async (paymentId: string) => {
    try {
      const detail = await fetchRecoveryDetail(paymentId);
      setSelectedRecord(detail);
    } catch (e) {
      console.error(e);
    }
  };

  const handleRunDemo = async (scenarioId: string) => {
    setLoadingDemo(scenarioId);
    try {
      const res = await runDemoScenario(scenarioId);
      await loadData();
      await handleSelectRecord(res.payment_id);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingDemo(null);
    }
  };

  // KPIs
  const totalCases = recoveries.length;
  const recoveredAmt = recoveries.filter(r => r.verification_status === 'recovered').reduce((acc, r) => acc + (r.recovered_amount || 0), 0);
  const atRiskAmt = recoveries.reduce((acc, r) => acc + (r.amount || 0), 0);
  const recoveryRate = totalCases > 0 ? ((recoveries.filter(r => r.verification_status === 'recovered').length / totalCases) * 100).toFixed(1) : '0.0';

  return (
    <div className="min-h-screen bg-background text-text font-sans flex flex-col">
      {/* Header */}
      <header className="border-b border-border bg-surface px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="bg-primary/20 p-2 rounded text-primary">
            <Activity size={20} />
          </div>
          <div>
            <h1 className="font-semibold text-lg leading-tight">RecoverAI</h1>
            <p className="text-muted text-xs">AI-Powered Revenue Recovery</p>
          </div>
        </div>
        <div className="flex gap-4 text-xs">
          <div className="flex items-center gap-1.5">
            <div className={clsx('w-2 h-2 rounded-full', health ? 'bg-success' : 'bg-danger')} />
            <span className="text-muted">API {health ? 'Connected' : 'Disconnected'}</span>
          </div>
          <div className="flex items-center gap-1.5 text-muted">
            <Server size={14} />
            <span>Mode: {health?.execution_mode || 'Unknown'}</span>
          </div>
        </div>
      </header>

      <main className="flex-1 p-6 flex flex-col gap-6">
        
        {/* Top Section: KPIs & Demos */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-surface border border-border rounded-lg p-4">
              <div className="text-muted text-xs mb-1">Revenue at Risk</div>
              <div className="text-2xl font-semibold">${atRiskAmt.toFixed(2)}</div>
            </div>
            <div className="bg-surface border border-border rounded-lg p-4">
              <div className="text-muted text-xs mb-1">Recovered Revenue</div>
              <div className="text-2xl font-semibold text-success">${recoveredAmt.toFixed(2)}</div>
            </div>
            <div className="bg-surface border border-border rounded-lg p-4">
              <div className="text-muted text-xs mb-1">Recovery Rate</div>
              <div className="text-2xl font-semibold">{recoveryRate}%</div>
            </div>
            <div className="bg-surface border border-border rounded-lg p-4">
              <div className="text-muted text-xs mb-1">Recovery Cases</div>
              <div className="text-2xl font-semibold">{totalCases}</div>
            </div>
          </div>
          
          <div className="bg-surface border border-border rounded-lg p-4 flex flex-col">
            <div className="text-xs font-semibold text-muted mb-3 uppercase tracking-wider">Run Demo Scenario</div>
            <div className="grid grid-cols-2 gap-2 flex-1">
              {Object.entries(demos).map(([key, demo]: any) => (
                <button 
                  key={key} 
                  onClick={() => handleRunDemo(key)}
                  disabled={loadingDemo !== null}
                  className="flex items-center gap-2 text-left bg-background hover:bg-border/50 border border-border rounded px-3 py-2 text-xs transition-colors disabled:opacity-50"
                  title={demo.description}
                >
                  <Play size={14} className={key === 'retry_limit_reached' ? 'text-danger' : 'text-primary'} />
                  <span className="truncate">{demo.name.split('—')[1]?.trim() || demo.name}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Pipeline Visual */}
        {selectedRecord && (
          <div className="bg-surface border border-border rounded-lg p-5">
            <div className="text-xs font-semibold text-muted mb-4 uppercase tracking-wider">Execution Pipeline — {selectedRecord.payment_id}</div>
            <div className="flex items-center justify-between text-sm">
              <PipelineStep title="Context" active={true} icon={<Box size={16}/>} />
              <ArrowRight size={16} className="text-muted flex-shrink-0 mx-2" />
              <PipelineStep title="AI Decision" active={true} subtitle={selectedRecord.selected_action} icon={<Activity size={16}/>} />
              <ArrowRight size={16} className="text-muted flex-shrink-0 mx-2" />
              
              {/* Policy Step - Critical Demo Area */}
              <div className={clsx("flex flex-col items-center flex-1 p-2 rounded border", 
                selectedRecord.policy_allowed ? "bg-success/10 border-success/20 text-success" : "bg-danger/10 border-danger/20 text-danger")}>
                <div className="flex items-center gap-1.5 font-medium mb-1">
                  {selectedRecord.policy_allowed ? <ShieldCheck size={16}/> : <ShieldAlert size={16}/>}
                  POLICY {selectedRecord.policy_allowed ? 'ALLOWED' : 'BLOCKED'}
                </div>
                <div className="text-xs opacity-80 text-center max-w-[150px] truncate" title={selectedRecord.policy_reason}>
                  {selectedRecord.policy_reason}
                </div>
              </div>

              <ArrowRight size={16} className="text-muted flex-shrink-0 mx-2" />
              <PipelineStep 
                title="Execution" 
                active={selectedRecord.policy_allowed} 
                subtitle={selectedRecord.policy_allowed ? selectedRecord.execution_status : 'NOT CALLED'} 
                icon={selectedRecord.policy_allowed ? <CheckCircle2 size={16}/> : <XCircle size={16} />}
                danger={!selectedRecord.policy_allowed}
              />
              <ArrowRight size={16} className="text-muted flex-shrink-0 mx-2" />
              <PipelineStep 
                title="Verification" 
                active={true} 
                subtitle={selectedRecord.verification_status} 
                icon={<Clock size={16}/>} 
              />
            </div>
          </div>
        )}

        {/* Lower Section: Table & Detail */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-[500px]">
          {/* Table */}
          <div className="lg:col-span-2 bg-surface border border-border rounded-lg flex flex-col overflow-hidden">
            <div className="p-4 border-b border-border font-medium text-sm flex items-center justify-between">
              <span>Recent Recoveries</span>
              <span className="text-xs text-muted font-normal">{recoveries.length} records</span>
            </div>
            <div className="overflow-auto flex-1">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="bg-background text-muted text-xs uppercase tracking-wider sticky top-0">
                  <tr>
                    <th className="px-4 py-3 font-medium">Payment ID</th>
                    <th className="px-4 py-3 font-medium">Amount</th>
                    <th className="px-4 py-3 font-medium">Failure</th>
                    <th className="px-4 py-3 font-medium">AI Action</th>
                    <th className="px-4 py-3 font-medium">Policy</th>
                    <th className="px-4 py-3 font-medium">Execution</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {recoveries.length === 0 ? (
                    <tr><td colSpan={6} className="p-8 text-center text-muted">No records found. Run a demo scenario.</td></tr>
                  ) : recoveries.map(r => (
                    <tr 
                      key={r.id} 
                      onClick={() => handleSelectRecord(r.payment_id)}
                      className={clsx(
                        "cursor-pointer hover:bg-border/30 transition-colors",
                        selectedRecord?.id === r.id && "bg-border/50"
                      )}
                    >
                      <td className="px-4 py-3 font-mono text-xs">{r.payment_id}</td>
                      <td className="px-4 py-3">${r.amount?.toFixed(2)}</td>
                      <td className="px-4 py-3 text-xs">{r.failure_type}</td>
                      <td className="px-4 py-3 font-mono text-xs text-primary">{r.selected_action}</td>
                      <td className="px-4 py-3">
                        <StatusBadge status={r.policy_allowed ? 'Allowed' : 'Blocked'} type="policy" />
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={r.execution_status} type="execution" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Detail Panel */}
          <div className="bg-surface border border-border rounded-lg overflow-y-auto">
            {selectedRecord ? (
              <div className="p-5 flex flex-col gap-6 text-sm">
                
                <div>
                  <h3 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Customer Context</h3>
                  <div className="grid grid-cols-2 gap-y-2 gap-x-4">
                    <div className="text-muted">Payment ID</div>
                    <div className="font-mono text-xs text-right">{selectedRecord.payment_id}</div>
                    <div className="text-muted">Amount</div>
                    <div className="text-right">${selectedRecord.amount?.toFixed(2)}</div>
                    <div className="text-muted">Failure Type</div>
                    <div className="text-right">{selectedRecord.failure_type}</div>
                    <div className="text-muted">Retry Count</div>
                    <div className="text-right">{selectedRecord.full_result?.recovery_analysis?.candidates ? selectedRecord.full_result.recovery_analysis.candidates.length > 0 ? "Analyzed" : "0" : "0"}</div>
                  </div>
                  {selectedRecord.full_result?.agent_decision?.reason && (
                    <div className="mt-3 p-3 bg-background rounded border border-border text-xs">
                      <div className="text-muted mb-1">AI Reason:</div>
                      {selectedRecord.full_result.agent_decision.reason}
                    </div>
                  )}
                </div>

                <div className="h-px bg-border w-full" />

                <div>
                  <h3 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Policy Engine</h3>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-muted">Decision</span>
                      <StatusBadge status={selectedRecord.policy_allowed ? 'Allowed' : 'Blocked'} type="policy" />
                    </div>
                    {!selectedRecord.policy_allowed && (
                      <div className="p-3 bg-danger/10 border border-danger/20 rounded text-danger text-xs flex gap-2 items-start">
                        <AlertCircle size={14} className="mt-0.5 flex-shrink-0" />
                        <span>{selectedRecord.policy_reason}</span>
                      </div>
                    )}
                    <div className="flex justify-between items-center">
                      <span className="text-muted">Requires Escalation</span>
                      <span>{selectedRecord.requires_escalation ? 'Yes' : 'No'}</span>
                    </div>
                  </div>
                </div>

                <div className="h-px bg-border w-full" />

                <div>
                  <h3 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Execution & Verification</h3>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-muted">Status</span>
                      <StatusBadge status={selectedRecord.execution_status} type="execution" />
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-muted">Provider</span>
                      <span className="font-mono text-xs">{selectedRecord.execution_provider}</span>
                    </div>
                    {selectedRecord.execution_provider_reference && (
                      <div className="flex justify-between items-center">
                        <span className="text-muted">Reference</span>
                        <span className="font-mono text-xs truncate max-w-[150px]" title={selectedRecord.execution_provider_reference}>
                          {selectedRecord.execution_provider_reference}
                        </span>
                      </div>
                    )}
                    <div className="flex justify-between items-center pt-2">
                      <span className="text-muted">Verification</span>
                      <StatusBadge status={selectedRecord.verification_status} type="verification" />
                    </div>
                  </div>
                </div>

              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-muted p-6 text-center">
                Select a recovery record to view details and decision logs.
              </div>
            )}
          </div>

        </div>
      </main>
    </div>
  );
}

function PipelineStep({ title, subtitle, active, icon, danger }: { title: string, subtitle?: string, active: boolean, icon: React.ReactNode, danger?: boolean }) {
  return (
    <div className={clsx(
      "flex flex-col items-center flex-1 p-2 rounded border",
      active 
        ? (danger ? "bg-danger/5 border-danger/20 text-danger" : "bg-background border-border text-text")
        : "bg-background/50 border-border/50 text-muted opacity-50"
    )}>
      <div className="flex items-center gap-1.5 font-medium mb-1">
        {icon}
        {title}
      </div>
      {subtitle && <div className="text-xs opacity-80 font-mono truncate max-w-[120px]" title={subtitle}>{subtitle}</div>}
    </div>
  );
}
