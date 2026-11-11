import L from 'leaflet'
import { useMemo } from 'react'
import { CircleMarker, MapContainer, Marker, Polygon, Polyline, TileLayer, Tooltip } from 'react-leaflet'
import type { Camp, Team, Ticket } from '../api'
import { COLORS, ticketColor, ticketLabel } from './ui'

export type Basemap = 'streets' | 'terrain' | 'satellite'

const BASEMAPS: Record<Basemap, { url: string; attribution: string; maxNativeZoom: number }> = {
  streets: {
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxNativeZoom: 19,
  },
  terrain: {
    url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, SRTM | style &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)',
    maxNativeZoom: 17,
  },
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri, Maxar, Earthstar Geographics and the GIS user community',
    maxNativeZoom: 19,
  },
}

interface Props {
  center: { lat: number; lng: number }
  river?: [number, number][]
  tickets?: Ticket[]
  teams?: Team[]
  camps?: Camp[]
  blocked?: { road: string; segments: [number, number][][] }[]
  zones?: { name: string; polygon: [number, number][] }[]
  preview?: [number, number][] | null
  selectedTicket?: string | null
  onSelectTicket?: (id: string) => void
  zoom?: number
  className?: string
  basemap?: Basemap
  // When given, the built-in zoom buttons are hidden and the caller draws its own.
  onMap?: (map: L.Map | null) => void
}

function teamIcon(team: Team, offset: number) {
  const short = team.kind === 'van' ? 'VAN' : `B${team.name.replace(/\D/g, '')}`
  const busy = team.status !== 'free'
  const bg = busy ? COLORS.accent : '#ffffff'
  const fg = busy ? '#ffffff' : '#1f3d39'
  return L.divIcon({
    className: 'team-icon',
    iconSize: [40, 22],
    iconAnchor: [20 - offset * 44, 11],
    html: `<div style="background:${bg};color:${fg};border:1.5px solid ${busy ? COLORS.accent : '#1f3d39'};border-radius:7px;font:700 11px 'Noto Sans',system-ui;text-align:center;line-height:19px;box-shadow:0 2px 6px rgba(0,0,0,.25)">${short}</div>`,
  })
}

function campIcon() {
  return L.divIcon({
    className: 'team-icon',
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    html: `<div style="background:#ffffff;border:2px solid ${COLORS.safe};border-radius:50%;width:26px;height:26px;font:700 13px system-ui;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(0,0,0,.25)">⛺</div>`,
  })
}

export default function WardMap(p: Props) {
  const basemap = BASEMAPS[p.basemap ?? 'streets']
  const visibleTickets = useMemo(
    () => (p.tickets ?? []).filter((t) => t.lat !== null && t.lng !== null && t.kind !== 'duplicate'),
    [p.tickets],
  )
  // Teams waiting at the same spot are drawn side by side instead of on top of each other.
  const offsets = useMemo(() => {
    const seen: Record<string, number> = {}
    const out: Record<string, number> = {}
    for (const t of p.teams ?? []) {
      const key = `${t.lat.toFixed(4)},${t.lng.toFixed(4)}`
      out[t.id] = seen[key] ?? 0
      seen[key] = (seen[key] ?? 0) + 1
    }
    return out
  }, [p.teams])
  return (
    <MapContainer center={[p.center.lat, p.center.lng]} zoom={p.zoom ?? 16} scrollWheelZoom
      className={p.className ?? 'h-full w-full'} attributionControl zoomControl={!p.onMap} ref={p.onMap}>
      <TileLayer key={p.basemap ?? 'streets'} attribution={basemap.attribution} url={basemap.url}
        maxNativeZoom={basemap.maxNativeZoom} maxZoom={20} className={`basemap-${p.basemap ?? 'streets'}`} />
      {p.zones?.map((z) => (
        <Polygon key={z.name} positions={z.polygon}
          pathOptions={{ color: COLORS.marigold, weight: 1.5, dashArray: '4 4', fillOpacity: 0.12 }}>
          <Tooltip>Watch zone: {z.name}</Tooltip>
        </Polygon>
      ))}
      {p.blocked?.map((b) => b.segments.map((seg, i) => (
        <Polyline key={`${b.road}-${i}`} positions={seg} pathOptions={{ color: COLORS.urgent, weight: 6, opacity: 0.9 }}>
          <Tooltip sticky>{b.road} blocked</Tooltip>
        </Polyline>
      )))}
      {p.teams?.map((t) => t.route && (
        <Polyline key={`route-${t.id}`} positions={t.route.coords}
          pathOptions={{ color: COLORS.accent, weight: 3.5, dashArray: '7 6', opacity: 0.95 }} />
      ))}
      {p.preview && <Polyline positions={p.preview} pathOptions={{ color: COLORS.marigold, weight: 5, dashArray: '8 6' }} />}
      {p.camps?.map((c) => (
        <Marker key={c.id} position={[c.lat, c.lng]} icon={campIcon()}>
          <Tooltip>{c.name}: {c.occupancy}/{c.capacity} people</Tooltip>
        </Marker>
      ))}
      {visibleTickets.map((t) => {
        const selected = t.id === p.selectedTicket
        // Open P1 families and the selected ticket carry a permanent label, like named places on a map.
        const labelled = selected || (t.priority === 'P1' && !['safe', 'closed', 'verify'].includes(t.status))
        return (
          <CircleMarker key={`${t.id}-${labelled ? 'l' : 'p'}`} center={[t.lat as number, t.lng as number]}
            radius={selected ? 11 : t.priority === 'P1' ? 8 : 6}
            eventHandlers={{ click: () => p.onSelectTicket?.(t.id) }}
            pathOptions={{ color: selected ? COLORS.accent : 'rgba(255,255,255,.9)', weight: selected ? 3 : 2, fillColor: ticketColor(t), fillOpacity: 0.95 }}>
            {labelled ? (
              <Tooltip permanent direction="right" offset={[8, 0]} className="pin-label">
                <span style={{ color: ticketColor(t) }}>●</span> {t.id}{t.people ? ` · ${t.people} ppl` : ''}
              </Tooltip>
            ) : (
              <Tooltip><b>{t.id}</b> {ticketLabel(t)}: {t.title}</Tooltip>
            )}
          </CircleMarker>
        )
      })}
      {p.teams?.map((t) => (
        <Marker key={t.id} position={[t.lat, t.lng]} icon={teamIcon(t, offsets[t.id] ?? 0)} zIndexOffset={1000}>
          <Tooltip>{t.name}: {t.status.replace('_', ' ')}{t.ticket_id ? ` (${t.ticket_id})` : ''}</Tooltip>
        </Marker>
      ))}
    </MapContainer>
  )
}
