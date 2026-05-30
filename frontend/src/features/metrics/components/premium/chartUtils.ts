export function smoothLinePath(pts: [number, number][]): string {
  if (pts.length === 0) return ''
  if (pts.length === 1) return `M ${pts[0][0]} ${pts[0][1]}`
  let d = `M ${pts[0][0].toFixed(2)} ${pts[0][1].toFixed(2)}`
  for (let i = 0; i < pts.length - 1; i++) {
    const x0 = i > 0 ? pts[i - 1][0] : pts[i][0]
    const y0 = i > 0 ? pts[i - 1][1] : pts[i][1]
    const x1 = pts[i][0], y1 = pts[i][1]
    const x2 = pts[i + 1][0], y2 = pts[i + 1][1]
    const x3 = i < pts.length - 2 ? pts[i + 2][0] : x2
    const y3 = i < pts.length - 2 ? pts[i + 2][1] : y2
    const cp1x = x1 + (x2 - x0) * 0.3
    const cp1y = y1 + (y2 - y0) * 0.3
    const cp2x = x2 - (x3 - x1) * 0.3
    const cp2y = y2 - (y3 - y1) * 0.3
    d += ` C ${cp1x.toFixed(2)},${cp1y.toFixed(2)} ${cp2x.toFixed(2)},${cp2y.toFixed(2)} ${x2.toFixed(2)},${y2.toFixed(2)}`
  }
  return d
}

export function smoothAreaPath(pts: [number, number][], baseline: number): string {
  if (pts.length < 2) return ''
  const line = smoothLinePath(pts)
  const last = pts[pts.length - 1]
  const first = pts[0]
  return `${line} L ${last[0].toFixed(2)},${baseline} L ${first[0].toFixed(2)},${baseline} Z`
}

export function mapToCanvas(
  values: number[],
  maxVal: number,
  left: number,
  right: number,
  top: number,
  bottom: number
): [number, number][] {
  const n = values.length
  if (n === 0) return []
  const xStep = n > 1 ? (right - left) / (n - 1) : 0
  return values.map((v, i) => [
    left + i * xStep,
    bottom - ((v / (maxVal || 1)) * (bottom - top)),
  ])
}
