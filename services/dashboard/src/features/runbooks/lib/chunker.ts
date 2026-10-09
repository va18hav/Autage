import MarkdownIt from 'markdown-it'
import type { RunbookCreate, RunbookSectionCreate } from '../../../shared/types/runbook'

export interface ChunkedSection extends RunbookSectionCreate {
  charCount: number
  tokenEstimate: number
}

export interface ChunkDiagnostics {
  totalSections: number
  totalChars: number
  estimatedTokens: number
  emptySections: string[]
  hasTitle: boolean
  hasService: boolean
}

export interface ChunkResult {
  title: string
  description: string | null
  service: string | null
  triggers: string[]
  rawContent: string
  sections: ChunkedSection[]
  diagnostics: ChunkDiagnostics
}

const md = new MarkdownIt()

/**
 * Extracts YAML frontmatter if present between leading --- markers.
 */
function parseFrontmatter(text: string): {
  frontmatter: Record<string, any>
  body: string
} {
  const match = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/)
  if (!match) {
    return { frontmatter: {}, body: text }
  }

  const rawYaml = match[1]
  const body = text.slice(match[0].length)
  const frontmatter: Record<string, any> = {}

  let currentKey: string | null = null
  let currentList: string[] | null = null

  for (const line of rawYaml.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) continue

    // List item under an active key
    if (trimmed.startsWith('- ') && currentKey && currentList) {
      currentList.push(trimmed.slice(2).trim().replace(/^['"]|['"]$/g, ''))
      continue
    }

    const colonIndex = trimmed.indexOf(':')
    if (colonIndex > 0) {
      const key = trimmed.slice(0, colonIndex).trim()
      const val = trimmed.slice(colonIndex + 1).trim()

      if (!val) {
        // likely a list follows
        currentKey = key
        currentList = []
        frontmatter[key] = currentList
      } else if (val.startsWith('[') && val.endsWith(']')) {
        // inline JSON-like array: [a, b, c]
        const items = val
          .slice(1, -1)
          .split(',')
          .map((s) => s.trim().replace(/^['"]|['"]$/g, ''))
          .filter(Boolean)
        frontmatter[key] = items
        currentKey = null
        currentList = null
      } else {
        frontmatter[key] = val.replace(/^['"]|['"]$/g, '')
        currentKey = null
        currentList = null
      }
    }
  }

  return { frontmatter, body }
}

/**
 * Chunks a markdown document into sequential sections using markdown-it's token stream.
 *
 * Rules:
 * 1. YAML frontmatter extracts title, service, triggers, description if provided.
 * 2. If the document starts with an H1 (# Title) and title was not set by frontmatter,
 *    it is adopted as the document title.
 * 3. Text before the first section heading is captured as an "Overview" section.
 * 4. Each subsequent heading (h1/h2/h3) creates a new chunk with its heading and body.
 */
export function chunkRunbookMarkdown(
  rawInput: string,
  overrides?: {
    title?: string
    service?: string
    triggers?: string[]
    description?: string
  },
): ChunkResult {
  const { frontmatter, body } = parseFrontmatter(rawInput.trim())
  const lines = body.split('\n')
  const tokens = md.parse(body, {})

  let detectedTitle = (overrides?.title ?? frontmatter.title ?? '').trim()
  const detectedService = (overrides?.service ?? frontmatter.service ?? '').trim()
  const detectedDescription = (overrides?.description ?? frontmatter.description ?? '').trim()

  let rawTriggers: string[] = []
  if (overrides?.triggers && overrides.triggers.length > 0) {
    rawTriggers = overrides.triggers
  } else if (Array.isArray(frontmatter.triggers)) {
    rawTriggers = frontmatter.triggers
  } else if (typeof frontmatter.triggers === 'string') {
    rawTriggers = frontmatter.triggers
      .split(',')
      .map((t: string) => t.trim())
      .filter(Boolean)
  }

  // Identify all headings with line boundaries
  interface HeadingMark {
    heading: string
    level: string
    lineStart: number
    lineEnd: number
  }

  const headingMarks: HeadingMark[] = []
  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i]
    if (token.type === 'heading_open') {
      const inline = tokens[i + 1]
      const headingText = inline?.content?.trim() ?? ''
      const lineStart = token.map ? token.map[0] : 0
      const lineEnd = token.map ? token.map[1] : lineStart + 1
      headingMarks.push({
        heading: headingText,
        level: token.tag,
        lineStart,
        lineEnd,
      })
    }
  }

  // If first heading is H1 and no title set yet, adopt it
  let firstHeadingIsDocTitle = false
  if (headingMarks.length > 0 && headingMarks[0].level === 'h1') {
    if (!detectedTitle) {
      detectedTitle = headingMarks[0].heading
    }
    firstHeadingIsDocTitle = true
  }

  const rawSections: { heading: string; content: string }[] = []

  if (headingMarks.length === 0) {
    // No headings found in the entire document
    if (body.trim()) {
      rawSections.push({
        heading: 'Overview',
        content: body.trim(),
      })
    }
  } else {
    // 1. Content before the first heading (if any)
    const firstHeadingLine = headingMarks[0].lineStart
    if (firstHeadingLine > 0) {
      const preContent = lines.slice(0, firstHeadingLine).join('\n').trim()
      if (preContent) {
        rawSections.push({
          heading: 'Overview',
          content: preContent,
        })
      }
    }

    // 2. Iterate through headings
    const startIndex = firstHeadingIsDocTitle ? 1 : 0

    // If first heading was H1 (used as title), check if there is content between it and next heading
    if (firstHeadingIsDocTitle) {
      const h1End = headingMarks[0].lineEnd
      const nextHeadingStart =
        headingMarks.length > 1 ? headingMarks[1].lineStart : lines.length
      const intro = lines.slice(h1End, nextHeadingStart).join('\n').trim()
      if (intro) {
        rawSections.push({
          heading: 'Overview',
          content: intro,
        })
      }
    }

    for (let i = startIndex; i < headingMarks.length; i++) {
      const current = headingMarks[i]
      const next = headingMarks[i + 1]
      const contentStart = current.lineEnd
      const contentEnd = next ? next.lineStart : lines.length
      const sectionContent = lines.slice(contentStart, contentEnd).join('\n').trim()

      rawSections.push({
        heading: current.heading || `Section ${rawSections.length + 1}`,
        content: sectionContent,
      })
    }
  }

  // Format into ChunkedSections with order_index and metrics
  const sections: ChunkedSection[] = rawSections.map((s, index) => {
    const charCount = s.content.length
    return {
      order_index: index,
      heading: s.heading.slice(0, 255),
      content: s.content,
      charCount,
      tokenEstimate: Math.max(1, Math.ceil(charCount / 4)),
    }
  })

  const totalChars = sections.reduce((sum, s) => sum + s.charCount, 0)
  const estimatedTokens = sections.reduce((sum, s) => sum + s.tokenEstimate, 0)
  const emptySections = sections
    .filter((s) => !s.content.trim())
    .map((s) => s.heading)

  return {
    title: detectedTitle,
    description: detectedDescription || null,
    service: detectedService || null,
    triggers: rawTriggers,
    rawContent: rawInput,
    sections,
    diagnostics: {
      totalSections: sections.length,
      totalChars,
      estimatedTokens,
      emptySections,
      hasTitle: Boolean(detectedTitle.trim()),
      hasService: Boolean(detectedService.trim()),
    },
  }
}

/**
 * Builds the payload ready to send to POST /api/runbooks
 */
export function toRunbookCreatePayload(chunkResult: ChunkResult): RunbookCreate {
  return {
    title: chunkResult.title.trim(),
    description: chunkResult.description?.trim() || null,
    service: chunkResult.service?.trim() || null,
    triggers: chunkResult.triggers.length > 0 ? chunkResult.triggers : null,
    raw_content: chunkResult.rawContent,
    sections: chunkResult.sections.map((s) => ({
      order_index: s.order_index,
      heading: s.heading.trim(),
      content: s.content.trim(),
    })),
  }
}
