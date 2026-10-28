'use client'

import React from 'react'
import {
  Activity, AlertTriangle, ArrowRight, CheckCircle2, Clock,
  Database, FileCheck2, GitBranch, Layers, ShieldCheck, Terminal
} from 'lucide-react'
import { api, PipelineCatalogItem } from '@/lib/api'
import { formatNumber, formatDateTime } from '@/lib/formatters'

export const DEFAULT_PIPELINE_CATALOG: PipelineCatalogItem[] = [
  {
    pipeline_name: 'rail_signal_orchestrator',
    display_name: 'Railway Signal Core Orchestrator',
    run_type: 'FULL_ETL',
    purpose: 'Complete eight-stage ETL pipeline loading station, train, schedule, and journey datasets into PostgreSQL.',
    source_datasets: ['stations.csv', 'trains.csv', 'schedules.csv', 'journey_train.parquet', 'journey_test.parquet'],
    destination_targets: ['stations', 'trains', 'schedules', 'journey_train', 'journey_test', 'pipeline_runs'],
    total_runs: 0,
    successful_runs: 0,
    failed_runs: 0,
    success_rate_pct: 0,
    current_status: 'REGISTERED',
    last_execution_time: null,
    latest_duration_seconds: null,
    avg_duration_seconds: null,
    failure_summary: null,
    is_schedulable: true,
  },
  {
    pipeline_name: 'rail_signal_validation',
    display_name: 'Preflight Safe Validation Audit',
    run_type: 'VALIDATION',
    purpose: 'Non-destructive advisory-locked data audit verifying referential integrity, record count baselines, and quality metrics.',
    source_datasets: ['data/processed/*.parquet', 'PostgreSQL relations'],
    destination_targets: ['pipeline_runs', 'data/reports/validation_audit.json'],
    total_runs: 0,
    successful_runs: 0,
    failed_runs: 0,
    success_rate_pct: 0,
    current_status: 'REGISTERED',
    last_execution_time: null,
    latest_duration_seconds: null,
    avg_duration_seconds: null,
    failure_summary: null,
    is_schedulable: true,
  },
  {
    pipeline_name: 'rail_signal_schema_validate',
    display_name: 'Schema Verification and Integrity Probe',
    run_type: 'SCHEMA_VALIDATE',
    purpose: 'Validates PostgreSQL tables, primary keys, foreign key constraints, indexes, and column nullability.',
    source_datasets: ['PostgreSQL information_schema'],
    destination_targets: ['schema inspection logs'],
    total_runs: 0,
    successful_runs: 0,
    failed_runs: 0,
    success_rate_pct: 0,
    current_status: 'REGISTERED',
    last_execution_time: null,
    latest_duration_seconds: null,
    avg_duration_seconds: null,
    failure_summary: null,
    is_schedulable: true,
  },
  {
    pipeline_name: 'rail_signal_schema_init',
    display_name: 'Relational Schema Initializer',
    run_type: 'SCHEMA_INIT',
    purpose: 'Executes DDL to initialize database schema, tables, audit log structures, and analytical indexes.',
    source_datasets: ['sql/init.sql', 'sql/schema.sql'],
    destination_targets: ['PostgreSQL DDL state'],
    total_runs: 0,
    successful_runs: 0,
    failed_runs: 0,
    success_rate_pct: 0,
    current_status: 'REGISTERED',
    last_execution_time: null,
    latest_duration_seconds: null,
    avg_duration_seconds: null,
    failure_summary: null,
    is_schedulable: false,
  },
  {
    pipeline_name: 'rail_signal_preflight',
    display_name: 'Preflight Environment and Dependency Inspector',
    run_type: 'INSPECT',
    purpose: 'Verifies database connectivity, table schema availability, file permissions, and directory structures.',
    source_datasets: ['filesystem', 'environment configuration'],
    destination_targets: ['diagnostic telemetry'],
    total_runs: 0,
    successful_runs: 0,
    failed_runs: 0,
    success_rate_pct: 0,
    current_status: 'REGISTERED',
    last_execution_time: null,
    latest_duration_seconds: null,
    avg_duration_seconds: null,
    failure_summary: null,
    is_schedulable: true,
  },
]

export function PipelineCatalogGrid({
  pipelines: propPipelines,
  selectedPipeline,
  onSelectPipeline,
}: {
  pipelines?: PipelineCatalogItem[]
  selectedPipeline?: string | null
  onSelectPipeline?: (pipelineName: string) => void
}) {
  const [catalog, setCatalog] = React.useState<PipelineCatalogItem[]>(
    propPipelines && propPipelines.length > 0 ? propPipelines : DEFAULT_PIPELINE_CATALOG
  )
  const [loading, setLoading] = React.useState(false)
  const [offlineNotice, setOfflineNotice] = React.useState(false)

  React.useEffect(() => {
    if (propPipelines && propPipelines.length > 0) {
      setCatalog(propPipelines)
      return
    }
    let active = true
    setLoading(true)
    api.getPipelines()
      .then((res) => {
        if (active && res?.pipelines && res.pipelines.length > 0) {
          setCatalog(res.pipelines)
          setOfflineNotice(false)
        }
      })
      .catch((err) => {
        console.warn('Failed to fetch pipeline catalog:', err)
        if (active) {
          setOfflineNotice(true)
          setCatalog(DEFAULT_PIPELINE_CATALOG)
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [propPipelines])

  const pipelines = catalog && catalog.length > 0 ? catalog : DEFAULT_PIPELINE_CATALOG

  return (
    <div>
      {offlineNotice && (
        <div className="pipeline-alert-banner alert-warn" style={{ marginBottom: 16 }}>
          <AlertTriangle style={{ width: 16, height: 16, flexShrink: 0, color: '#8a5717' }} />
          <div className="pipeline-alert-content">
            <div className="pipeline-alert-title">FastAPI Offline — Static Registry Fallback</div>
            <p className="pipeline-alert-msg">
              Displaying registered pipeline architectural definitions. Live execution counts, durations, and timestamps are currently unavailable until the FastAPI backend is running.
            </p>
          </div>
        </div>
      )}

      <div className="pipeline-catalog-grid">
        {pipelines.map((p) => {
          const isSelected = selectedPipeline === p.pipeline_name
          const statusTone = offlineNotice
            ? 'neutral'
            : p.current_status === 'SUCCESS' ? 'good' : p.current_status === 'FAILED' ? 'error' : 'neutral'
          const displayStatus = offlineNotice ? 'OFFLINE' : p.current_status
          const durationFormatted = p.latest_duration_seconds !== null && p.latest_duration_seconds !== undefined
            ? `${p.latest_duration_seconds.toFixed(2)}s`
            : '—'

          return (
            <div
              key={p.pipeline_name}
              className={`catalog-card ${isSelected ? 'selected' : ''}`}
              style={isSelected ? { borderColor: 'var(--charcoal)', boxShadow: '0 0 0 1px var(--charcoal)' } : {}}
            >
              <div>
                <div className="catalog-card-head">
                  <div>
                    <span className="type-chip" style={{ fontSize: 9.5 }}>{p.run_type}</span>
                    <h3 className="catalog-title" style={{ marginTop: 6 }}>{p.display_name}</h3>
                    <code style={{ fontSize: 10, color: 'var(--muted)', fontFamily: 'monospace' }}>{p.pipeline_name}</code>
                  </div>
                  <span className={`pipeline-status-badge status-${displayStatus.toLowerCase()}`}>
                    <span className={`sys-status-indicator pulse-${statusTone}`} />
                    {displayStatus}
                  </span>
                </div>

                <p className="catalog-purpose">{p.purpose}</p>

                {/* Source Datasets & Destination Targets */}
                <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 6, fontSize: 10.5 }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                    <span style={{ color: 'var(--muted)', fontWeight: 600, width: 75, flexShrink: 0 }}>Sources:</span>
                    <span style={{ color: 'var(--ink)', fontFamily: 'monospace', fontSize: 10 }}>
                      {p.source_datasets.slice(0, 3).join(', ')}{p.source_datasets.length > 3 ? ` +${p.source_datasets.length - 3}` : ''}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                    <span style={{ color: 'var(--muted)', fontWeight: 600, width: 75, flexShrink: 0 }}>Targets:</span>
                    <span style={{ color: 'var(--ink)', fontFamily: 'monospace', fontSize: 10 }}>
                      {p.destination_targets.slice(0, 3).join(', ')}{p.destination_targets.length > 3 ? ` +${p.destination_targets.length - 3}` : ''}
                    </span>
                  </div>
                </div>
              </div>

              {/* Run Stats */}
              <div>
                <div className="catalog-stats-row">
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <span style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase', fontWeight: 600 }}>Total Runs</span>
                    <b style={{ fontSize: 12, fontFamily: 'monospace', color: offlineNotice ? 'var(--muted)' : 'inherit' }}>
                      {offlineNotice ? '—' : formatNumber(p.total_runs)}
                    </b>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <span style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase', fontWeight: 600 }}>Success Rate</span>
                    <b style={{ fontSize: 12, fontFamily: 'monospace', color: offlineNotice ? 'var(--muted)' : p.success_rate_pct >= 90 ? '#436316' : p.success_rate_pct > 0 ? '#8a5717' : 'inherit' }}>
                      {offlineNotice ? '—' : p.total_runs > 0 ? `${p.success_rate_pct}%` : '—'}
                    </b>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <span style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase', fontWeight: 600 }}>Duration</span>
                    <b style={{ fontSize: 12, fontFamily: 'monospace', color: offlineNotice ? 'var(--muted)' : 'inherit' }}>
                      {offlineNotice ? '—' : durationFormatted}
                    </b>
                  </div>
                </div>

                {!offlineNotice && p.failure_summary && (
                  <div style={{ marginTop: 8, padding: '6px 8px', background: '#fdf3f2', border: '1px solid #eed0ce', borderRadius: 3, fontSize: 10, color: '#8e2b26' }}>
                    <span style={{ fontWeight: 600 }}>Last failure: </span>
                    <span style={{ fontFamily: 'monospace' }}>{p.failure_summary}</span>
                  </div>
                )}

                <div className="catalog-foot">
                  <span>
                    {offlineNotice ? (
                      <span style={{ color: '#8a5717' }}>Telemetry offline · Start backend to sync</span>
                    ) : p.last_execution_time ? (
                      <>Last run: {formatDateTime(p.last_execution_time)}</>
                    ) : (
                      'Never executed'
                    )}
                  </span>

                  {onSelectPipeline && !offlineNotice && (
                    <button
                      type="button"
                      className="catalog-filter-btn"
                      onClick={() => onSelectPipeline(isSelected ? 'ALL' : p.pipeline_name)}
                    >
                      {isSelected ? 'Clear Filter' : 'Filter History →'}
                    </button>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
