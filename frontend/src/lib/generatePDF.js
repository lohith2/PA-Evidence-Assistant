import { jsPDF } from 'jspdf'

/**
 * Generates and downloads a formatted prior auth appeal PDF.
 *
 * @param {object} params
 * @param {string} params.appealLetter  - Full letter text
 * @param {Array}  params.citations     - Citation objects with .source and .title
 * @param {string} [params.claimId]
 * @param {string} [params.drug]
 * @param {string} [params.payer]
 * @param {number} [params.confidenceScore] - 0–1
 * @param {string} [params.sessionId]
 * @returns {string} The generated filename
 */
export function generateAppealPDF({
  appealLetter,
  citations = [],
  claimId,
  drug,
  payer,
  confidenceScore,
  sessionId,
}) {
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'letter' })

  const pageW = doc.internal.pageSize.getWidth()
  const pageH = doc.internal.pageSize.getHeight()
  const margin = 25.4   // 1-inch margins
  const contentW = pageW - margin * 2
  let y = margin

  // ── Header bar ─────────────────────────────────────────────────
  doc.setFillColor(15, 23, 36)
  doc.rect(0, 0, pageW, 18, 'F')

  doc.setTextColor(255, 255, 255)
  doc.setFontSize(11)
  doc.setFont('helvetica', 'bold')
  doc.text('PRIOR AUTHORIZATION APPEAL', margin, 11)

  doc.setFontSize(8)
  doc.setFont('helvetica', 'normal')
  doc.text(
    `PA Evidence Assistant · Generated ${new Date().toLocaleDateString('en-US', {
      year: 'numeric', month: 'long', day: 'numeric',
    })}`,
    pageW - margin,
    11,
    { align: 'right' },
  )

  y = 28

  // ── Case info block ────────────────────────────────────────────
  doc.setTextColor(55, 65, 81)
  doc.setFontSize(8)
  doc.setFont('helvetica', 'normal')

  const infoLines = [
    `Claim ID: ${claimId || 'See denial letter'}`,
    `Drug / Procedure: ${drug || 'See denial letter'}`,
    `Payer: ${payer || 'See denial letter'}`,
    `Evidence confidence: ${confidenceScore != null ? Math.round(confidenceScore * 100) + '%' : 'N/A'}`,
    `Session: ${sessionId || 'N/A'}`,
  ]

  infoLines.forEach(line => {
    doc.text(line, margin, y)
    y += 5
  })

  y += 4

  // Divider
  doc.setDrawColor(226, 232, 240)
  doc.setLineWidth(0.3)
  doc.line(margin, y, pageW - margin, y)
  y += 8

  // ── Letter body ────────────────────────────────────────────────
  doc.setTextColor(17, 24, 39)
  doc.setFontSize(10)
  doc.setFont('helvetica', 'normal')

  const bodyLines = doc.splitTextToSize(appealLetter || '', contentW)

  const addContinuationHeader = () => {
    doc.setFillColor(15, 23, 36)
    doc.rect(0, 0, pageW, 12, 'F')
    doc.setTextColor(255, 255, 255)
    doc.setFontSize(7)
    doc.setFont('helvetica', 'normal')
    doc.text(`Appeal Letter — ${drug || ''} — Continued`, margin, 8)
    doc.setTextColor(17, 24, 39)
    doc.setFontSize(10)
  }

  bodyLines.forEach(line => {
    if (y > pageH - margin - 20) {
      doc.addPage()
      y = margin
      addContinuationHeader()
      y = 20
    }
    doc.text(line, margin, y)
    y += 5.5
  })

  y += 8

  // ── Citations section ──────────────────────────────────────────
  if (citations.length > 0) {
    if (y > pageH - margin - 40) {
      doc.addPage()
      y = margin + 15
    }

    doc.setDrawColor(226, 232, 240)
    doc.setLineWidth(0.3)
    doc.line(margin, y, pageW - margin, y)
    y += 7

    doc.setFontSize(8)
    doc.setFont('helvetica', 'bold')
    doc.setTextColor(55, 65, 81)
    doc.text('EVIDENCE SOURCES', margin, y)
    y += 6

    doc.setFont('helvetica', 'normal')
    doc.setFontSize(7.5)

    const SOURCE_COLORS = {
      FDA:            [180, 83, 9],
      CMS:            [29, 78, 216],
      GUIDELINES:     [21, 128, 61],
      PAYER:          [71, 85, 105],
      PAYER_POLICIES: [180, 83, 9],
      AHA:            [185, 28, 28],
      ADA:            [91, 33, 182],
      ASCO:           [109, 40, 217],
      AAN:            [12, 74, 110],
      ACR:            [21, 128, 61],
      USPSTF:         [15, 118, 110],
    }

    // Deduplicate
    const seen = new Set()
    const uniqueCitations = citations.filter(c => {
      const key = `${c.source}|${c.title}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })

    uniqueCitations.forEach(citation => {
      if (y > pageH - margin - 10) {
        doc.addPage()
        y = margin + 15
      }

      const srcKey = (citation.source || '').toUpperCase().split(' ')[0]
      const color = SOURCE_COLORS[srcKey] || [75, 85, 99]
      const badge = `[${srcKey}]`
      const badgeW = doc.getTextWidth(badge)

      doc.setTextColor(...color)
      doc.setFont('helvetica', 'bold')
      doc.text(badge, margin, y)

      doc.setTextColor(55, 65, 81)
      doc.setFont('helvetica', 'normal')
      const titleLines = doc.splitTextToSize(
        citation.title || 'Untitled',
        contentW - badgeW - 2,
      )
      doc.text(titleLines, margin + badgeW + 2, y)
      y += titleLines.length * 4.5 + 1.5
    })
  }

  // ── Footer on every page ───────────────────────────────────────
  const totalPages = doc.internal.getNumberOfPages()
  for (let p = 1; p <= totalPages; p++) {
    doc.setPage(p)
    doc.setFontSize(7)
    doc.setTextColor(156, 163, 175)
    doc.setFont('helvetica', 'normal')
    doc.text(
      `PA Evidence Assistant · For clinical review only · Page ${p} of ${totalPages}`,
      pageW / 2,
      pageH - 10,
      { align: 'center' },
    )
    doc.text(
      'Review and verify all citations before submission',
      pageW / 2,
      pageH - 6,
      { align: 'center' },
    )
  }

  // ── Filename & save ────────────────────────────────────────────
  const drugSlug = (drug || 'appeal')
    .split('(')[0]
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '')

  const dateSlug = new Date().toISOString().split('T')[0]
  const filename = `appeal-${drugSlug}-${dateSlug}.pdf`

  doc.save(filename)
  return filename
}
