import L from 'leaflet'
import { useMemo } from 'react'
import { CircleMarker, MapContainer, Marker, Polygon, Polyline, TileLayer, Tooltip } from 'react-leaflet'
import type { Camp, Team, Ticket } from '../api'
import { COLORS, ticketColor, ticketLabel } from './ui'

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
}

function teamIcon(team: Team, offset: number) {
  const short = team.kind === 'van' ? 'VAN' : `B${team.name.replace(/\D/g, '')}`
  const busy = team.status !== 'free'
  return L.divIcon({
    className: 'team-icon',
    iconSize: [34, 20],
    iconAnchor: [17 - offset * 38, 10],
    html: `<div style="background:${busy ? COLORS.ink : '#fff'};color:${busy ? '#fff' : COLORS.ink};border:2px solid ${COLORS.ink};border-radius:6px;font:700 11px system-ui;text-align:center;line-height:16px;box-shadow:0 1px 4px rgba(0,0,0,.35)">${short}</div>`,
  })
}

function campIcon() {
  return L.divIcon({
    className: 'team-icon',
    iconSize: [22, 22],
    iconAnchor: [11, 11],
    html: `<div style="background:${COLORS.safe};color:#fff;border-radius:50%;width:22px;height:22px;font:700 12px system-ui;display:flex;align-items:center;justify-content:center;box-shadow:0 1px 4px rgba(0,0,0,.35)">⛺</div>`,
  })
}

export default function WardMap(p: Props) {
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
      className={p.className ?? 'h-full w-full'} attributionControl>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {p.zones?.map((z) => (
        <Polygon key={z.name} positions={z.polygon}
          pathOptions={{ color: COLORS.marigold, weight: 1, dashArray: '4 4', fillOpacity: 0.12 }}>
          <Tooltip>Watch zone: {z.name}</Tooltip>
        </Polygon>
      ))}
      {p.blocked?.map((b) => b.segments.map((seg, i) => (
        <Polyline key={`${b.road}-${i}`} positions={seg} pathOptions={{ color: COLORS.urgent, weight: 6, opacity: 0.85 }}>
          <Tooltip sticky>{b.road} blocked</Tooltip>
        </Polyline>
      )))}
      {p.teams?.map((t) => t.route && (
        <Polyline key={`route-${t.id}`} positions={t.route.coords}
          pathOptions={{ color: COLORS.ink, weight: 3, dashArray: '6 5', opacity: 0.8 }} />
      ))}
      {p.preview && <Polyline positions={p.preview} pathOptions={{ color: COLORS.marigold, weight: 5, dashArray: '8 6' }} />}
      {p.camps?.map((c) => (
        <Marker key={c.id} position={[c.lat, c.lng]} icon={campIcon()}>
          <Tooltip>{c.name}: {c.occupancy}/{c.capacity} people</Tooltip>
        </Marker>
      ))}
      {visibleTickets.map((t) => (
        <CircleMarker key={t.id} center={[t.lat as number, t.lng as number]}
          radius={t.id === p.selectedTicket ? 12 : t.priority === 'P1' ? 9 : 7}
          eventHandlers={{ click: () => p.onSelectTicket?.(t.id) }}
          pathOptions={{ color: '#fff', weight: 2, fillColor: ticketColor(t), fillOpacity: 0.95 }}>
          <Tooltip>
            <b>{t.id}</b> {ticketLabel(t)}: {t.title}
          </Tooltip>
        </CircleMarker>
      ))}
      {p.teams?.map((t) => (
        <Marker key={t.id} position={[t.lat, t.lng]} icon={teamIcon(t, offsets[t.id] ?? 0)} zIndexOffset={1000}>
          <Tooltip>{t.name}: {t.status.replace('_', ' ')}{t.ticket_id ? ` (${t.ticket_id})` : ''}</Tooltip>
        </Marker>
      ))}
    </MapContainer>
  )
}
