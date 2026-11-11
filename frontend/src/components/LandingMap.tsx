import L from 'leaflet'
import { Circle, MapContainer, Marker, Polygon, Polyline, TileLayer } from 'react-leaflet'

export interface Overview {
  ward: { name: string; city: string; incident_name: string; center: { lat: number; lng: number }; river: [number, number][] }
  incident: { level: string; status: string }
  clock: string
  roads: { road: string; segments: [number, number][][] }[]
  blocked_roads: { road: string; segments: [number, number][][] }[]
  watch_zones: { name: string; polygon: [number, number][] }[]
  camps: { name: string; lat: number; lng: number; capacity: number; occupancy: number }[]
  landmarks: { name: string; lat: number; lng: number }[]
  totals: { reports_in: number; families_safe: number; boats_out: number; boats: number; people_in_camps: number }
}

const INK = '#1f3d39'
const TEAL = '#2f5d58'
const CORAL = '#d4705f'
const SANS = "'Noto Sans','Noto Sans Devanagari',system-ui,sans-serif"
const SERIF = "'Noto Serif','Noto Serif Devanagari',Georgia,serif"

function esc(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string)
}

function campIcon(label: string, sub: string) {
  return L.divIcon({
    className: 'team-icon', iconSize: [0, 0], iconAnchor: [0, 0],
    html: `<div style="position:relative">
      <span style="position:absolute;left:-15px;top:-15px;width:30px;height:30px;border:1.5px solid ${TEAL};border-radius:50%;background:rgba(246,249,247,.55)"></span>
      <span style="position:absolute;left:-3.5px;top:-3.5px;width:7px;height:7px;background:${TEAL};border-radius:50%"></span>
      <span style="position:absolute;left:15px;top:-1px;width:34px;height:1px;background:${TEAL};opacity:.7"></span>
      <span style="position:absolute;left:54px;top:-13px;white-space:nowrap;font:600 11.5px ${SERIF};color:${INK}">${esc(label)}</span>
      <span style="position:absolute;left:54px;top:3px;white-space:nowrap;font:600 9.5px ${SANS};letter-spacing:.1em;text-transform:uppercase;color:#4f6560">${esc(sub)}</span>
    </div>`,
  })
}

function landmarkIcon(name: string) {
  return L.divIcon({
    className: 'team-icon', iconSize: [0, 0], iconAnchor: [0, 0],
    html: `<div style="position:relative">
      <span style="position:absolute;left:-3px;top:-3px;width:6px;height:6px;background:${INK};transform:rotate(45deg)"></span>
      <span style="position:absolute;left:8px;top:-7px;white-space:nowrap;font:600 9.5px ${SANS};letter-spacing:.1em;color:${INK};opacity:.8;text-transform:uppercase">${esc(name)}</span>
    </div>`,
  })
}

// A large ring with a leader line and a two-line note, like the annotations on a survey plate.
function calloutIcon(title: string, note: string, flip = false) {
  const side = flip ? 'right:44px;text-align:right' : 'left:44px'
  const line = flip ? 'right:34px' : 'left:34px'
  return L.divIcon({
    className: 'team-icon', iconSize: [0, 0], iconAnchor: [0, 0],
    html: `<div style="position:relative">
      <span style="position:absolute;left:-34px;top:-34px;width:68px;height:68px;border:1.5px dashed ${CORAL};border-radius:50%;background:rgba(212,112,95,.08)"></span>
      <span style="position:absolute;left:-4.5px;top:-4.5px;width:9px;height:9px;background:${CORAL};border-radius:50%;box-shadow:0 0 0 4px rgba(212,112,95,.22)"></span>
      <span style="position:absolute;${line};top:-1px;width:30px;height:1px;background:${CORAL}"></span>
      <div style="position:absolute;${side};top:-30px;width:184px;background:rgba(246,249,247,.9);border:1px solid rgba(31,61,57,.18);padding:6px 9px">
        <div style="font:600 12px ${SERIF};color:${INK}">${esc(title)}</div>
        <div style="margin-top:2px;font:400 10.5px/1.45 ${SANS};color:#4f6560">${esc(note)}</div>
      </div>
    </div>`,
  })
}

// The water's reach: a band around the river, wider on the low north bank.
function floodBand(river: [number, number][]): [number, number][] {
  if (river.length < 2) return []
  const north = river.map(([la, ln], i) => [la + 0.0021 + (i % 2) * 0.0004, ln] as [number, number])
  const south = [...river].reverse().map(([la, ln], i) => [la - 0.0009 - (i % 2) * 0.0002, ln] as [number, number])
  const first = river[0], last = river[river.length - 1]
  return [[first[0], first[1] - 0.002], ...north, [last[0], last[1] + 0.002], ...south]
}

const CALLOUTS = [
  { title: 'Three reports, one ticket', note: 'A daughter, a neighbour and a voice note about one house, merged', flip: false },
  { title: 'Road blocked', note: 'Every boat on it rerouted before it sets out', flip: true },
  { title: 'Rumour held', note: '“Dam gate opened” sent to Verify, not to a boat', flip: false },
]

export default function LandingMap({ data, offsetLng = 0 }: { data: Overview | null; offsetLng?: number }) {
  const center = data?.ward.center ?? { lat: 19.077, lng: 72.877 }
  const river = data?.ward.river ?? []
  const lm = data?.landmarks ?? []
  const routeRoads = (data?.roads ?? []).filter((r) => ['Lane 4', 'Station Road'].includes(r.road))
  return (
    <MapContainer key={offsetLng} center={[center.lat, center.lng + offsetLng]} zoom={16} className="h-full w-full"
      dragging={false} zoomControl={false} scrollWheelZoom={false} doubleClickZoom={false} touchZoom={false}
      boxZoom={false} keyboard={false} attributionControl>
      <TileLayer className="landing-sat" maxNativeZoom={19}
        url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        attribution="Imagery &copy; Esri, Maxar, Earthstar Geographics" />
      <Circle center={[center.lat, center.lng]} radius={260} pathOptions={{ color: TEAL, weight: 1.2, opacity: 0.45, dashArray: '2 6', fill: false }} />
      <Circle center={[center.lat, center.lng]} radius={520} pathOptions={{ color: TEAL, weight: 1.2, opacity: 0.3, dashArray: '2 8', fill: false }} />
      {river.length > 1 && (
        <>
          <Polygon positions={floodBand(river)} pathOptions={{ color: CORAL, weight: 1.2, opacity: 0.8, fillColor: '#e4a596', fillOpacity: 0.38 }} />
          <Polyline positions={river} pathOptions={{ color: '#a9c9d2', weight: 14, opacity: 0.45 }} />
          <Polyline positions={river} pathOptions={{ color: '#5f8fa0', weight: 2.5, opacity: 0.9 }} />
        </>
      )}
      {data?.watch_zones.map((z) => (
        <Polygon key={z.name} positions={z.polygon} pathOptions={{ color: '#c68a2e', weight: 1, dashArray: '4 4', fillOpacity: 0.1 }} />
      ))}
      {data?.roads.map((r) => r.segments.map((seg, i) => (
        <Polyline key={`${r.road}-${i}`} positions={seg} pathOptions={{ color: TEAL, weight: 2, opacity: 0.8 }} />
      )))}
      {routeRoads.map((r) => r.segments.map((seg, i) => (
        <Polyline key={`route-${r.road}-${i}`} positions={seg}
          pathOptions={{ color: CORAL, weight: 3, opacity: 1, dashArray: '8 6', className: 'dash-move' }} />
      )))}
      {data?.blocked_roads.map((b) => b.segments.map((seg, i) => (
        <Polyline key={`blocked-${b.road}-${i}`} positions={seg} pathOptions={{ color: '#c8443c', weight: 3, dashArray: '3 5', opacity: 0.95 }} />
      )))}
      {lm.map((l) => <Marker key={l.name} position={[l.lat, l.lng]} icon={landmarkIcon(l.name)} interactive={false} />)}
      {data?.camps.map((c) => (
        <Marker key={c.name} position={[c.lat, c.lng]} interactive={false}
          icon={campIcon(c.name.split(' (')[0], `${c.occupancy}/${c.capacity} people`)} />
      ))}
      {CALLOUTS.map((c, i) => lm[i * 2] && (
        <Marker key={c.title} position={[lm[i * 2].lat, lm[i * 2].lng]} interactive={false} zIndexOffset={500} icon={calloutIcon(c.title, c.note, c.flip)} />
      ))}
    </MapContainer>
  )
}
