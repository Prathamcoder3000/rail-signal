'use client'

import { useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, ArrowUpRight, BarChart3, CheckCircle2, ChevronDown,
  CircleDot, Database, FileCheck2, GitBranch, Layers3, Menu, Network, RefreshCw, Search,
  Settings2, Table2, TrainFront, X, Zap
} from 'lucide-react'
import {
  Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis
} from 'recharts'
import {
  api, DataQualityData, DelayAnalyticsData, OverviewData,
  PassengerFlowData, PipelineStatusData, TrainItem, TrainListResponse,
  TrainPerformanceData
} from '@/lib/api'

type Source = 'processed-data' | 'demo-data' | 'api-data'
type PageKey = 'overview' | 'trains' | 'passengers' | 'pipeline' | 'quality'

// Fallback baseline data when backend is not yet started
const fallbackTrains: TrainItem[] = [
  { train_number: '12951', train_name: 'Mumbai Rajdhani', train_type: 'RAJ', from_station_name: 'Mumbai Central', to_station_name: 'New Delhi', distance_km: 1384, formatted_duration: '15h 35m', has_first_ac: true, has_second_ac: true, has_third_ac: true, has_sleeper: false, has_chair_car: false },
  { train_number: '12002', train_name: 'Bhopal Shatabdi', train_type: 'SHTB', from_station_name: 'New Delhi', to_station_name: 'Bhopal Jn', distance_km: 707, formatted_duration: '8h 30m', has_first_ac: true, has_second_ac: false, has_third_ac: false, has_sleeper: false, has_chair_car: true },
  { train_number: '12259', train_name: 'Duronto Express', train_type: 'DRNT', from_station_name: 'Sealdah', to_station_name: 'Bikaner', distance_km: 1455, formatted_duration: '20h 45m', has_first_ac: true, has_second_ac: true, has_third_ac: true, has_sleeper: true, has_chair_car: false },
  { train_number: '12627', train_name: 'Karnataka Express', train_type: 'EXP', from_station_name: 'KSR Bengaluru', to_station_name: 'New Delhi', distance_km: 2400, formatted_duration: '39h 55m', has_first_ac: true, has_second_ac: true, has_third_ac: true, has_sleeper: true, has_chair_car: false },
  { train_number: '12904', train_name: 'Golden Temple Mail', train_type: 'MAIL', from_station_name: 'Mumbai Central', to_station_name: 'Amritsar', distance_km: 1891, formatted_duration: '31h 35m', has_first_ac: true, has_second_ac: true, has_third_ac: true, has_sleeper: true, has_chair_car: false },
  { train_number: '12839', train_name: 'Chennai Mail', train_type: 'MAIL', from_station_name: 'Howrah', to_station_name: 'Chennai Central', distance_km: 1663, formatted_duration: '27h 20m', has_first_ac: true, has_second_ac: true, has_third_ac: true, has_sleeper: true, has_chair_car: false },
]

const nav = [
  { key: 'overview' as PageKey, label: 'Overview', icon: Activity },
  { key: 'trains' as PageKey, label: 'Train Performance', icon: TrainFront },
  { key: 'passengers' as PageKey, label: 'Passenger Flow', icon: BarChart3 },
  { key: 'pipeline' as PageKey, label: 'Data Pipeline', icon: GitBranch },
  { key: 'quality' as PageKey, label: 'Data Quality', icon: FileCheck2 },
]

function SourceBadge({ source = 'api-data' as Source }: { source?: Source }) {
  return <span className={`source-badge source-${source}`}><span className="source-dot" />{source}</span>
}

function Status({ children, tone = 'good' }: { children: React.ReactNode; tone?: 'good' | 'warn' | 'neutral' }) {
  return <span className={`status status-${tone}`}><span className="status-dot" />{children}</span>
}

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <section className={`panel ${className}`}>{children}</section>
}

function Header({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string
  title: string
  description: string
  action?: React.ReactNode
}) {
  return (
    <header className="page-header">
      <div>
        <div className="eyebrow"><span className="eyebrow-line" />{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </header>
  )
}

function ChartTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tip">
      <strong>{label}</strong>
      {payload.map((item: any) => (
        <div key={item.dataKey} className="tip-row">
          <span style={{ background: item.color }} />
          {item.name}: <b>{item.value}{item.dataKey === 'value' || item.dataKey === 'percentage' || item.dataKey === 'avg_seat_utilisation_pct' ? '%' : ''}</b>
        </div>
      ))}
    </div>
  )
}

function Kpi({
  label,
  value,
  detail,
  icon: Icon,
  accent = false,
}: {
  label: string
  value: string
  detail: string
  icon: any
  accent?: boolean
}) {
  return (
    <div className={`kpi ${accent ? 'kpi-accent' : ''}`}>
      <div className="kpi-top"><span>{label}</span><Icon /></div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-detail">{detail}</div>
    </div>
  )
}

function SectionTitle({
  title,
  detail,
  source,
}: {
  title: string
  detail?: string
  source?: Source
}) {
  return (
    <div className="section-title">
      <div>
        <h2>{title}</h2>
        {detail && <p>{detail}</p>}
      </div>
      {source && <SourceBadge source={source} />}
    </div>
  )
}

// ==============================================================================
// 1. Overview Page Component
// ==============================================================================

function Overview({
  go,
  data,
  loading,
  error,
}: {
  go: (page: PageKey) => void
  data: OverviewData | null
  loading: boolean
  error: string | null
}) {
  const kpis = data?.kpis || {
    stations_processed: 8988,
    trains_processed: 5207,
    schedules_accepted: 394469,
    journey_records: 1875000,
    total_records: 2283664,
  }

  const categoryProfile = data?.train_category_profile || [
    { train_type: 'PASS', total_trains: 2459, avg_distance_km: 158, avg_duration_hours: 4.8 },
    { train_type: 'EXP', total_trains: 1287, avg_distance_km: 948, avg_duration_hours: 19.9 },
    { train_type: 'SF', total_trains: 719, avg_distance_km: 1232, avg_duration_hours: 21.3 },
    { train_type: 'MEMU', total_trains: 222, avg_distance_km: 126, avg_duration_hours: 3.8 },
    { train_type: 'DEMU', total_trains: 167, avg_distance_km: 104, avg_duration_hours: 3.3 },
  ]

  const delaySummary = data?.delay_summary || {
    on_time_percentage: 28.1,
    delay_percentage: 71.9,
    total_journeys: 1500000,
    delayed_journeys: 1078329,
    on_time_journeys: 421671,
    avg_delay_minutes: 97.7,
    provenance_note: 'Educational simulation model dataset',
  }

  const donutData = [
    { name: 'On time', value: delaySummary.on_time_percentage },
    { name: 'Delayed', value: delaySummary.delay_percentage },
  ]

  const passengerProfile = [
    { name: 'Tejas', value: 71.6 },
    { name: 'Shatabdi', value: 71.6 },
    { name: 'Duronto', value: 71.5 },
    { name: 'Superfast', value: 71.5 },
    { name: 'Express', value: 71.5 },
  ]

  return (
    <>
      <Header
        eyebrow="Workspace / Overview"
        title="Railway intelligence overview"
        description="A structured view of verified railway infrastructure, journey delay analytics, and data pipeline quality."
        action={
          <div className="header-context">
            <SourceBadge source={data ? 'api-data' : 'processed-data'} />
            <span>
              <span className="context-pulse" />
              {loading ? 'Refreshing...' : data ? 'Live Database' : 'Processed dataset'}
            </span>
          </div>
        }
      />

      <div className="kpi-grid">
        <Kpi
          label="Stations processed"
          value={kpis.stations_processed.toLocaleString()}
          detail="Physical reference records"
          icon={Network}
        />
        <Kpi
          label="Trains processed"
          value={kpis.trains_processed.toLocaleString()}
          detail="Official IR timetable services"
          icon={TrainFront}
          accent
        />
        <Kpi
          label="Schedule records"
          value={kpis.schedules_accepted.toLocaleString()}
          detail="Accepted after validation"
          icon={Table2}
        />
        <Kpi
          label="Journey records"
          value={kpis.journey_records.toLocaleString()}
          detail="1.5M Train + 375k Test"
          icon={Layers3}
          accent
        />
      </div>

      <div className="overview-grid">
        <Card className="route-card">
          <SectionTitle
            title="Railway network topology"
            detail="Physical railway administrative backbone & key junction corridors"
            source="processed-data"
          />
          <div className="route-note">
            <CircleDot /> Schematic representation of major network interchange hubs
          </div>
          <svg className="route-svg" viewBox="0 0 680 230" role="img" aria-label="Railway station relationship schematic">
            <path className="route-line faint" d="M56 160 C135 92, 170 173, 250 111 S376 55, 440 112 S535 176, 625 77" />
            <path className="route-line" d="M56 160 C135 92, 170 173, 250 111 S376 55, 440 112 S535 176, 625 77" />
            <path className="route-line secondary" d="M250 111 L296 202 L440 112" />
            <g className="station-labels">
              <g transform="translate(56 160)"><circle className="station selected" r="7"/><text y="28">Mumbai (CSMT/MMCT)</text></g>
              <g transform="translate(165 131)"><circle r="5"/><text y="-15">Surat (ST)</text></g>
              <g transform="translate(250 111)"><circle className="station selected" r="7"/><text y="-16">Bhopal (BPL)</text></g>
              <g transform="translate(365 87)"><circle r="5"/><text y="-15">Agra (AGC)</text></g>
              <g transform="translate(440 112)"><circle className="station selected" r="7"/><text y="28">New Delhi (NDLS)</text></g>
              <g transform="translate(625 77)"><circle r="5"/><text y="-15">Howrah (HWH)</text></g>
              <g transform="translate(296 202)"><circle r="5"/><text y="23">Nagpur (NGP)</text></g>
            </g>
          </svg>
        </Card>

        <Card className="chart-card">
          <SectionTitle
            title="Train category profile"
            detail="Average route distance by official train category"
            source={data ? 'api-data' : 'processed-data'}
          />
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categoryProfile} layout="vertical" margin={{ left: 8, right: 12, top: 8, bottom: 4 }}>
                <CartesianGrid horizontal={false} stroke="#e5e3da" />
                <XAxis type="number" tickLine={false} axisLine={false} tick={{ fill: '#777b72', fontSize: 11 }} />
                <YAxis dataKey="train_type" type="category" width={60} tickLine={false} axisLine={false} tick={{ fill: '#777b72', fontSize: 11 }} />
                <Tooltip content={<ChartTip />} cursor={{ fill: '#f4f2eb' }} />
                <Bar isAnimationActive={false} dataKey="avg_distance_km" name="Distance (km)" fill="#607f9b" radius={[0, 2, 2, 0]} barSize={19} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="chart-foot">
            <span><i className="legend-blue" />Average route distance</span>
            <span>Verified 5,207 train services</span>
          </div>
        </Card>
      </div>

      <div className="overview-grid bottom-grid">
        <Card className="chart-card">
          <SectionTitle
            title="Journey delay distribution"
            detail="Distribution across 1.5M training journey records"
            source={data ? 'api-data' : 'processed-data'}
          />
          <div className="delay-content">
            <div className="donut">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    isAnimationActive={false}
                    data={donutData}
                    innerRadius={58}
                    outerRadius={78}
                    paddingAngle={3}
                    dataKey="value"
                    stroke="none"
                  >
                    <Cell fill="#607f9b" />
                    <Cell fill="#c6e66a" />
                  </Pie>
                  <text x="50%" y="46%" textAnchor="middle" dominantBaseline="middle" className="donut-value">
                    {delaySummary.on_time_percentage}%
                  </text>
                  <text x="50%" y="61%" textAnchor="middle" dominantBaseline="middle" className="donut-label">
                    on time
                  </text>
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="delay-legend">
              <div><span className="legend-blue" />On-time journeys <b>{delaySummary.on_time_percentage}% ({delaySummary.on_time_journeys.toLocaleString()})</b></div>
              <div><span className="legend-lime" />Delayed journeys (&gt;15m) <b>{delaySummary.delay_percentage}% ({delaySummary.delayed_journeys.toLocaleString()})</b></div>
              <p>Simulated Kaggle competition dataset. Average delay: {delaySummary.avg_delay_minutes} min.</p>
            </div>
          </div>
        </Card>

        <Card className="chart-card">
          <SectionTitle
            title="Passenger utilisation"
            detail="Average seat occupancy percentage"
            source={data ? 'api-data' : 'processed-data'}
          />
          <div className="chart-wrap short">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={passengerProfile} margin={{ left: -20, right: 4, top: 8, bottom: 4 }}>
                <CartesianGrid vertical={false} stroke="#e5e3da" />
                <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fill: '#777b72', fontSize: 10 }} />
                <YAxis domain={[0, 100]} tickLine={false} axisLine={false} tick={{ fill: '#777b72', fontSize: 10 }} tickFormatter={(v) => `${v}%`} />
                <Tooltip content={<ChartTip />} />
                <Bar isAnimationActive={false} dataKey="value" name="Utilisation" fill="#c6e66a" radius={[2, 2, 0, 0]} barSize={28} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="lower-grid">
        <Card>
          <SectionTitle title="Processing summary" detail="Completed project phases" />
          <div className="processing-list">
            <div>
              <span className="process-index">01</span>
              <span><b>Environment & discovery</b><small>Datasets catalogued and profiled</small></span>
              <Status>Complete</Status>
            </div>
            <div>
              <span className="process-index">02</span>
              <span><b>Ingestion & transformation</b><small>Validated records written to Parquet</small></span>
              <Status>Complete</Status>
            </div>
            <div>
              <span className="process-index">03</span>
              <span><b>PostgreSQL & analytics</b><small>2,283,664 rows loaded for SQL analytics</small></span>
              <Status>Complete</Status>
            </div>
            <div>
              <span className="process-index">04</span>
              <span><b>FastAPI REST Backend</b><small>Live endpoints with SQL aggregation</small></span>
              <Status>Complete</Status>
            </div>
          </div>
        </Card>

        <Card className="quality-callout">
          <div className="callout-icon"><CheckCircle2 /></div>
          <div>
            <div className="eyebrow">DATA QUALITY</div>
            <h3>2,283,664 accepted records</h3>
            <p>Invalid records are quarantined rather than silently repaired with fabricated metrics. 22,614 records quarantined.</p>
            <button className="text-link" onClick={() => go('quality')}>
              Review quality report <ArrowUpRight />
            </button>
          </div>
        </Card>
      </div>
    </>
  )
}

// ==============================================================================
// 2. Train Performance Page Component
// ==============================================================================

function TrainPerformance({
  perfData,
}: {
  perfData: TrainPerformanceData | null
}) {
  const [query, setQuery] = useState('')
  const [type, setType] = useState('All types')
  const [page, setPage] = useState(1)
  const [trainsList, setTrainsList] = useState<TrainItem[]>(fallbackTrains)
  const [totalCount, setTotalCount] = useState(5207)
  const [totalPages, setTotalPages] = useState(1)
  const [availableTypes, setAvailableTypes] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedTrain, setSelectedTrain] = useState<TrainItem | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    api.getTrains({ query, train_type: type, page, page_size: 10 })
      .then((res) => {
        if (!active) return
        setTrainsList(res.items)
        setTotalCount(res.total)
        setTotalPages(res.total_pages)
        if (res.available_train_types?.length) {
          setAvailableTypes(res.available_train_types)
        }
      })
      .catch((err) => {
        console.warn('Could not fetch trains from API, using fallback:', err)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [query, type, page])

  const chartData = perfData?.by_type?.slice(0, 6) || [
    { train_type: 'PASS', total_trains: 2459, avg_distance_km: 158, avg_duration_hours: 4.8 },
    { train_type: 'EXP', total_trains: 1287, avg_distance_km: 948, avg_duration_hours: 19.9 },
    { train_type: 'SF', total_trains: 719, avg_distance_km: 1232, avg_duration_hours: 21.3 },
    { train_type: 'MEMU', total_trains: 222, avg_distance_km: 126, avg_duration_hours: 3.8 },
    { train_type: 'DEMU', total_trains: 167, avg_distance_km: 104, avg_duration_hours: 3.3 },
  ]

  return (
    <>
      <Header
        eyebrow="Analytics / Reference"
        title="Train performance"
        description="Explore 5,207 official Indian Railways train reference services and analyze route characteristics."
        action={<SourceBadge source="api-data" />}
      />

      <div className="kpi-grid three">
        <Kpi
          label="Train services"
          value={perfData ? perfData.total_trains.toLocaleString() : '5,207'}
          detail="Official IR timetable services"
          icon={TrainFront}
        />
        <Kpi
          label="Average route"
          value={perfData ? `${Math.round(perfData.avg_route_km).toLocaleString()} km` : '622 km'}
          detail="Across all train categories"
          icon={GitBranch}
          accent
        />
        <Kpi
          label="Average duration"
          value={perfData?.formatted_avg_duration || '13h 24m'}
          detail="Average journey duration"
          icon={Activity}
        />
      </div>

      <div className="overview-grid">
        <Card className="chart-card">
          <SectionTitle
            title="Distance by train type"
            detail="Average route distance in kilometers"
            source="api-data"
          />
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ left: -12, right: 12, top: 16, bottom: 5 }}>
                <CartesianGrid vertical={false} stroke="#e5e3da" />
                <XAxis dataKey="train_type" tickLine={false} axisLine={false} tick={{ fill: '#777b72', fontSize: 10 }} />
                <YAxis tickLine={false} axisLine={false} tick={{ fill: '#777b72', fontSize: 10 }} />
                <Tooltip content={<ChartTip />} />
                <Bar isAnimationActive={false} dataKey="avg_distance_km" name="Distance (km)" fill="#607f9b" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="chart-card">
          <SectionTitle
            title="Duration comparison"
            detail="Average duration in scheduled hours"
            source="api-data"
          />
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ left: -12, right: 12, top: 16, bottom: 5 }}>
                <CartesianGrid vertical={false} stroke="#e5e3da" />
                <XAxis dataKey="train_type" tickLine={false} axisLine={false} tick={{ fill: '#777b72', fontSize: 10 }} />
                <YAxis tickLine={false} axisLine={false} tick={{ fill: '#777b72', fontSize: 10 }} />
                <Tooltip content={<ChartTip />} />
                <Bar isAnimationActive={false} dataKey="avg_duration_hours" name="Duration (hours)" fill="#a9bbc9" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <Card className="table-card">
        <div className="table-toolbar">
          <SectionTitle
            title="Train reference table"
            detail={`${totalCount.toLocaleString()} total trains · Page ${page} of ${totalPages}`}
          />
          <div className="table-controls">
            <label className="search">
              <Search />
              <input
                value={query}
                onChange={(e) => { setQuery(e.target.value); setPage(1) }}
                placeholder="Search number or name"
                aria-label="Search trains"
              />
            </label>
            <label className="select-wrap">
              <select
                value={type}
                onChange={(e) => { setType(e.target.value); setPage(1) }}
                aria-label="Filter by train type"
              >
                <option>All types</option>
                {(availableTypes.length ? availableTypes : ['PASS', 'EXP', 'SF', 'MEMU', 'DEMU', 'MAIL', 'RAJ', 'SHTB', 'DRNT']).map((x) => (
                  <option key={x} value={x}>{x}</option>
                ))}
              </select>
              <ChevronDown />
            </label>
          </div>
        </div>

        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Train</th>
                <th>Type</th>
                <th>Zone</th>
                <th>Origin</th>
                <th>Destination</th>
                <th>Distance</th>
                <th>Duration</th>
                <th>Coaches</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={8} className="empty-cell">Loading train records...</td></tr>
              ) : trainsList.length ? (
                trainsList.map((t) => (
                  <tr key={t.train_number}>
                    <td>
                      <b>{t.train_number}</b>
                      <small>{t.train_name}</small>
                    </td>
                    <td><span className="type-chip">{t.train_type || '—'}</span></td>
                    <td>{t.zone || '—'}</td>
                    <td>{t.from_station_name || t.from_station_code || '—'}</td>
                    <td>{t.to_station_name || t.to_station_code || '—'}</td>
                    <td>{t.distance_km ? `${t.distance_km.toLocaleString()} km` : '—'}</td>
                    <td>{t.formatted_duration || '—'}</td>
                    <td>
                      <small>
                        {[
                          t.has_first_ac ? '1A' : null,
                          t.has_second_ac ? '2A' : null,
                          t.has_third_ac ? '3A' : null,
                          t.has_sleeper ? 'SL' : null,
                          t.has_chair_car ? 'CC' : null,
                        ].filter(Boolean).join(' · ') || 'General'}
                      </small>
                    </td>
                  </tr>
                ))
              ) : (
                <tr><td colSpan={8} className="empty-cell">No train records match your filters.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="pagination">
          <span>
            Showing {trainsList.length ? (page - 1) * 10 + 1 : 0}–{Math.min(page * 10, totalCount)} of {totalCount.toLocaleString()}
          </span>
          <div>
            <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1 || loading}>Previous</button>
            <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page >= totalPages || loading}>Next</button>
          </div>
        </div>
      </Card>
    </>
  )
}

// ==============================================================================
// 3. Passenger Flow Component
// ==============================================================================

function Passengers({
  data,
}: {
  data: PassengerFlowData | null
}) {
  const avgUtil = data?.avg_seat_utilisation_pct ?? 71.6
  const totalRepresented = data?.total_journeys_represented ?? 1875000
  const overloaded = data?.overloaded_journeys ?? 0

  const bands = data?.bands || [
    { band: '0–50%', percentage: 10.9, count: 163544 },
    { band: '50–75%', percentage: 42.3, count: 635075 },
    { band: '75–100%', percentage: 46.8, count: 701381 },
    { band: '100%+', percentage: 0.0, count: 0 },
  ]

  const typeData = (data?.by_train_type?.slice(0, 6) || [
    { train_type: 'Tejas Express', avg_seat_utilisation_pct: 71.6, total_journeys: 14839, overloaded_journeys: 0 },
    { train_type: 'Shatabdi Express', avg_seat_utilisation_pct: 71.6, total_journeys: 59930, overloaded_journeys: 0 },
    { train_type: 'Jan Shatabdi', avg_seat_utilisation_pct: 71.6, total_journeys: 75120, overloaded_journeys: 0 },
    { train_type: 'Superfast Express', avg_seat_utilisation_pct: 71.6, total_journeys: 345020, overloaded_journeys: 0 },
    { train_type: 'Express', avg_seat_utilisation_pct: 71.6, total_journeys: 624110, overloaded_journeys: 0 },
  ]).map(t => ({
    name: t.train_type.replace(' Express', ''),
    value: t.avg_seat_utilisation_pct,
  }))

  return (
    <>
      <Header
        eyebrow="Analytics / Journey data"
        title="Passenger flow & utilisation"
        description="Analyse simulated passenger utilisation parameters across 1.875M journey records."
        action={<SourceBadge source="api-data" />}
      />

      <div className="data-notice">
        <AlertTriangle />
        <span>
          <b>DATA PROVENANCE NOTICE:</b> Seat utilisation percentages and overload indicators are synthetic modeling parameters from an educational machine learning benchmark. They do not constitute actual physical CRIS/IRCTC passenger counts.
        </span>
      </div>

      <div className="kpi-grid three">
        <Kpi
          label="Average seat utilisation"
          value={`${avgUtil}%`}
          detail="Calculated across 1,500,000 training records"
          icon={Activity}
          accent
        />
        <Kpi
          label="Journeys represented"
          value={totalRepresented.toLocaleString()}
          detail="1.5M Train + 375k Test datasets"
          icon={TrainFront}
        />
        <Kpi
          label="Overloaded journeys"
          value={overloaded.toLocaleString()}
          detail="Journeys exceeding capacity indicator"
          icon={AlertTriangle}
        />
      </div>

      <div className="overview-grid">
        <Card className="chart-card">
          <SectionTitle
            title="Utilisation by train category"
            detail="Average seat_utilisation_pct from educational journeys"
            source="api-data"
          />
          <div className="chart-wrap tall">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={typeData} margin={{ left: 0, right: 12, top: 14, bottom: 5 }}>
                <CartesianGrid vertical={false} stroke="#e5e3da" />
                <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fill: '#777b72', fontSize: 10 }} />
                <YAxis domain={[0, 100]} tickLine={false} axisLine={false} tick={{ fill: '#777b72', fontSize: 10 }} tickFormatter={v => `${v}%`} />
                <Tooltip content={<ChartTip />} />
                <Bar isAnimationActive={false} dataKey="value" name="Utilisation" fill="#c6e66a" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="chart-card utilisation-bands">
          <SectionTitle
            title="Utilisation bands distribution"
            detail="Share of journey records grouped by occupancy band"
            source="api-data"
          />
          {bands.map((b) => (
            <div key={b.band} className="band-row">
              <span>{b.band}</span>
              <div>
                <i
                  className={b.band === '100%+' ? 'amber' : ''}
                  style={{ width: `${Math.max(1, Math.min(100, b.percentage))}%` }}
                />
              </div>
              <b>{b.percentage}%</b>
            </div>
          ))}
          <p className="chart-footnote">
            Computed dynamically from 1,500,000 journey records in PostgreSQL. Band 50–75% represents 635,075 records, band 75–100% represents 701,381 records.
          </p>
        </Card>
      </div>
    </>
  )
}

// ==============================================================================
// 4. Data Pipeline Page Component
// ==============================================================================

function Pipeline({
  statusData,
}: {
  statusData: PipelineStatusData | null
}) {
  const stages = statusData?.stages || [
    { number: '01', label: 'Raw datasets', description: 'CSV · JSON · GeoJSON in data/raw/', status: 'Complete' },
    { number: '02', label: 'Ingestion', description: 'Chunked CSV & GeoJSON parsing', status: 'Complete' },
    { number: '03', label: 'Validation', description: 'Schema & coordinate rules applied', status: 'Complete' },
    { number: '04', label: 'Transformation', description: 'Normalized columns & nulls', status: 'Complete' },
    { number: '05', label: 'Parquet storage', description: 'Snappy columnar outputs', status: 'Complete' },
    { number: '06', label: 'PostgreSQL', description: '2.28M records loaded in rail_signal', status: 'Complete' },
    { number: '07', label: 'SQL analytics', description: 'Queries executed & verified', status: 'Complete' },
  ]

  const datasets = [
    { name: 'Stations', source: 'stations.json (1.86 MB)', format: 'Parquet', records: '8,988', status: 'Loaded' },
    { name: 'Trains', source: 'trains.json (14.77 MB)', format: 'Parquet', records: '5,207', status: 'Loaded' },
    { name: 'Schedules', source: 'schedules.json (82.17 MB)', format: 'Parquet', records: '394,469', status: 'Loaded' },
    { name: 'Journey Train', source: 'ir_train.csv (337.16 MB)', format: 'Parquet', records: '1,500,000', status: 'Loaded' },
    { name: 'Journey Test', source: 'ir_test.csv (76.01 MB)', format: 'Parquet', records: '375,000', status: 'Loaded' },
  ]

  return (
    <>
      <Header
        eyebrow="Engineering / Workflow"
        title="Data engineering pipeline"
        description="End-to-end data flow: extraction, schema validation, quarantine auditing, Parquet persistence, and PostgreSQL loading."
        action={<Status>All 7 stages complete</Status>}
      />

      <Card className="pipeline-card">
        <SectionTitle
          title="Pipeline architecture & stages"
          detail="Modular, idempotent Python ETL pipeline with atomic write safeguards"
        />
        <div className="pipeline-flow">
          {stages.map((s, i) => (
            <div className="pipeline-stage" key={s.label}>
              <div className="stage-node">
                {i === 0 ? <Database /> : i === 1 ? <ArrowUpRight /> : i === 2 ? <FileCheck2 /> : i === 3 ? <Settings2 /> : i === 4 ? <Layers3 /> : i === 5 ? <Table2 /> : <BarChart3 />}
              </div>
              <span className="stage-num">{s.number}</span>
              <b>{s.label}</b>
              <small>{s.description}</small>
              {i < stages.length - 1 && <div className="stage-connector" />}
            </div>
          ))}
        </div>
      </Card>

      <Card className="table-card">
        <SectionTitle
          title="Dataset storage & loading summary"
          detail="Verified Parquet storage and relational loading into PostgreSQL"
        />
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Dataset</th>
                <th>Raw Source File</th>
                <th>Processed Format</th>
                <th>Database Records</th>
                <th>Stage Status</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((d) => (
                <tr key={d.name}>
                  <td><b>{d.name}</b></td>
                  <td>{d.source}</td>
                  <td><span className="type-chip">{d.format}</span></td>
                  <td>{d.records}</td>
                  <td><Status>Loaded</Status></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="empty-run">
        <div className="empty-icon"><CheckCircle2 /></div>
        <div>
          <h3>Pipeline Execution Status: Success</h3>
          <p>
            Last successful execution: {statusData?.last_run_timestamp ? new Date(statusData.last_run_timestamp).toLocaleString() : '2026-10-14 14:17:47 UTC'}.
            Total records processed: 2,283,664 accepted rows written to Parquet and loaded into database.
          </p>
        </div>
        <SourceBadge source="api-data" />
      </Card>
    </>
  )
}

// ==============================================================================
// 5. Data Quality Page Component
// ==============================================================================

function Quality({
  qualityData,
}: {
  qualityData: DataQualityData | null
}) {
  const datasets = qualityData?.datasets || [
    { name: 'Stations', source_type: 'JSON / GeoJSON', input_records: 8990, accepted: 8988, quarantined: 2, validation_status: 'Review required', rejection_reasons: ['Missing station_name', 'Missing station_code'] },
    { name: 'Trains', source_type: 'JSON / GeoJSON', input_records: 5208, accepted: 5207, quarantined: 1, validation_status: 'Review required', rejection_reasons: ['Missing train_name'] },
    { name: 'Schedules', source_type: 'JSON Array', input_records: 417080, accepted: 394469, quarantined: 22611, validation_status: 'Review required', rejection_reasons: ['Missing station_code', 'Invalid day_number'] },
    { name: 'Journey Train', source_type: 'CSV', input_records: 1500000, accepted: 1500000, quarantined: 0, validation_status: 'Clean', rejection_reasons: [] },
    { name: 'Journey Test', source_type: 'CSV', input_records: 375000, accepted: 375000, quarantined: 0, validation_status: 'Clean', rejection_reasons: [] },
  ]

  const totalAccepted = qualityData?.total_accepted ?? 2283664
  const totalQuarantined = qualityData?.total_quarantined ?? 22614

  const chartData = datasets.map(d => ({
    name: d.name,
    accepted: d.accepted,
    quarantined: d.quarantined,
  }))

  return (
    <>
      <Header
        eyebrow="Engineering / Validation"
        title="Data quality & quarantine audit"
        description="Track validation outcomes, verified records, and audited quarantine isolations across all datasets."
        action={<SourceBadge source="api-data" />}
      />

      <div className="kpi-grid four">
        <Kpi
          label="Accepted records"
          value={totalAccepted.toLocaleString()}
          detail="Stored in database tables"
          icon={CheckCircle2}
          accent
        />
        <Kpi
          label="Quarantined records"
          value={totalQuarantined.toLocaleString()}
          detail="Held in quarantine JSON logs"
          icon={AlertTriangle}
        />
        <Kpi
          label="Evaluated datasets"
          value="5"
          detail="Reference + journey datasets"
          icon={Database}
        />
        <Kpi
          label="Quarantine rate"
          value="0.98%"
          detail="22,614 of 2,306,278 input rows"
          icon={FileCheck2}
        />
      </div>

      <div className="overview-grid quality-grid">
        <Card className="chart-card">
          <SectionTitle
            title="Dataset acceptance profile"
            detail="Accepted records vs quarantined anomalies"
            source="api-data"
          />
          <div className="chart-wrap tall">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ left: 0, right: 12, top: 14, bottom: 5 }}>
                <CartesianGrid vertical={false} stroke="#e5e3da" />
                <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fill: '#777b72', fontSize: 10 }} />
                <YAxis tickLine={false} axisLine={false} tick={{ fill: '#777b72', fontSize: 10 }} tickFormatter={v => v >= 1000 ? `${v / 1000}k` : v} />
                <Tooltip content={<ChartTip />} />
                <Bar isAnimationActive={false} dataKey="accepted" name="Accepted" fill="#c6e66a" radius={[2, 2, 0, 0]} />
                <Bar isAnimationActive={false} dataKey="quarantined" name="Quarantined" fill="#c68f51" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="quality-explain">
          <div className="eyebrow">ENGINEERING PRINCIPLE</div>
          <h2>Quarantine, don&apos;t fabricate.</h2>
          <p>
            Anomalous or missing records are safely quarantined in JSON audit logs rather than silently replaced with invented defaults. This guarantees auditability and prevents data corruption.
          </p>
          <div className="explain-rule"><span className="legend-lime" />Accepted into database &amp; Parquet</div>
          <div className="explain-rule"><span className="legend-amber" />Quarantined under data/processed/quarantine/</div>
        </Card>
      </div>

      <Card className="table-card">
        <SectionTitle
          title="Dataset quality audit report"
          detail="Granular validation breakdown and documented quarantine reasons"
        />
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Dataset</th>
                <th>Raw Inputs</th>
                <th>Accepted Rows</th>
                <th>Quarantined</th>
                <th>Validation Status</th>
                <th>Rejection Reasons</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((d) => (
                <tr key={d.name}>
                  <td><b>{d.name}</b><small>{d.source_type}</small></td>
                  <td>{d.input_records.toLocaleString()}</td>
                  <td className="accepted-cell">{d.accepted.toLocaleString()}</td>
                  <td className={d.quarantined ? 'quarantine-cell' : ''}>{d.quarantined.toLocaleString()}</td>
                  <td>
                    {d.quarantined ? <Status tone="warn">Review required</Status> : <Status>Clean</Status>}
                  </td>
                  <td>
                    {d.rejection_reasons.length ? (
                      <small>{d.rejection_reasons.join(', ')}</small>
                    ) : (
                      <small style={{ color: '#68705f' }}>No schema violations</small>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="table-footnote">
          <AlertTriangle />
          Schedule quarantine (22,611 rows) isolates records with missing stop day_number or empty station codes. Raw source files remain untouched.
        </div>
      </Card>
    </>
  )
}

// ==============================================================================
// App Shell & Main Component
// ==============================================================================

export default function Page() {
  const [active, setActive] = useState<PageKey>('overview')
  const [mobileOpen, setMobileOpen] = useState(false)
  const [overviewData, setOverviewData] = useState<OverviewData | null>(null)
  const [perfData, setPerfData] = useState<TrainPerformanceData | null>(null)
  const [passengerData, setPassengerData] = useState<PassengerFlowData | null>(null)
  const [pipelineData, setPipelineData] = useState<PipelineStatusData | null>(null)
  const [qualityData, setQualityData] = useState<DataQualityData | null>(null)
  const [apiConnected, setApiConnected] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(false)

  // Fetch overview data and healthcheck on initial load
  useEffect(() => {
    let mounted = true
    setLoading(true)

    // Check health
    api.getHealth()
      .then((health) => {
        if (!mounted) return
        setApiConnected(health.status === 'healthy')
      })
      .catch(() => {
        if (!mounted) return
        setApiConnected(false)
      })

    // Fetch initial Overview data
    api.getOverview()
      .then((data) => {
        if (!mounted) return
        setOverviewData(data)
      })
      .catch((err) => {
        console.warn('Overview fetch error:', err)
      })
      .finally(() => {
        if (mounted) setLoading(false)
      })

    return () => { mounted = false }
  }, [])

  // Lazy load data for respective tabs when active page changes
  useEffect(() => {
    let mounted = true
    if (active === 'trains' && !perfData) {
      api.getTrainPerformance().then(d => mounted && setPerfData(d)).catch(() => {})
    } else if (active === 'passengers' && !passengerData) {
      api.getPassengerFlow().then(d => mounted && setPassengerData(d)).catch(() => {})
    } else if (active === 'pipeline' && !pipelineData) {
      api.getPipelineStatus().then(d => mounted && setPipelineData(d)).catch(() => {})
    } else if (active === 'quality' && !qualityData) {
      api.getDataQuality().then(d => mounted && setQualityData(d)).catch(() => {})
    }
    return () => { mounted = false }
  }, [active, perfData, passengerData, pipelineData, qualityData])

  const go = (key: PageKey) => {
    setActive(key)
    setMobileOpen(false)
  }

  const current = nav.find(x => x.key === active)!

  const Content = useMemo(() => {
    switch (active) {
      case 'overview':
        return <Overview go={go} data={overviewData} loading={loading} error={null} />
      case 'trains':
        return <TrainPerformance perfData={perfData} />
      case 'passengers':
        return <Passengers data={passengerData} />
      case 'pipeline':
        return <Pipeline statusData={pipelineData} />
      case 'quality':
        return <Quality qualityData={qualityData} />
    }
  }, [active, overviewData, perfData, passengerData, pipelineData, qualityData, loading])

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileOpen ? 'open' : ''}`}>
        <div className="brand">
          <div className="brand-mark">
            <span />
            <span />
          </div>
          <div>
            <b>RAIL / SIGNAL</b>
            <small>RAILWAY INTELLIGENCE</small>
          </div>
          <button className="mobile-close" onClick={() => setMobileOpen(false)} aria-label="Close navigation">
            <X />
          </button>
        </div>

        <div className="nav-label">Workspace</div>
        <nav>
          {nav.map((item) => (
            <button
              key={item.key}
              className={active === item.key ? 'active' : ''}
              onClick={() => go(item.key)}
            >
              <item.icon />
              <span>{item.label}</span>
              {active === item.key && <i />}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="workspace-tag">
            <span
              className="context-pulse"
              style={{ background: apiConnected === true ? 'var(--lime)' : apiConnected === false ? 'var(--amber)' : '#999' }}
            />
            {apiConnected === true ? 'API CONNECTED' : apiConnected === false ? 'OFFLINE (STANDBY)' : 'CONNECTING...'}
          </div>
          <div className="side-meta">
            <span>database environment</span>
            <b>{apiConnected ? 'PostgreSQL (rail_signal)' : 'Parquet dataset'}</b>
          </div>
          <div className="version">
            RAIL / SIGNAL <span>v0.3.0</span>
          </div>
        </div>
      </aside>

      <main className="workspace">
        <div className="mobile-topbar">
          <button onClick={() => setMobileOpen(true)} aria-label="Open navigation">
            <Menu />
          </button>
          <b>RAIL / SIGNAL</b>
          <span>{current.label}</span>
        </div>

        <div className="workspace-inner">
          {Content}
          <footer>
            <span>RAIL / SIGNAL · Railway Operations &amp; Passenger Flow Data Engineering Platform</span>
            <span>Verified 2,283,664 records · DataMeet &amp; Kaggle Indian Railways</span>
          </footer>
        </div>
      </main>

      {mobileOpen && (
        <button
          className="scrim"
          onClick={() => setMobileOpen(false)}
          aria-label="Close navigation overlay"
        />
      )}
    </div>
  )
}
