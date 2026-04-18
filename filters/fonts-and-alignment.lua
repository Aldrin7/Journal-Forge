-- PaperForge — Lua Filter: fonts-and-alignment.lua
-- Dynamically maps typographic styles to journal requirements.
-- Applied via Pandoc AST transformation.

-- Track journal context (set by the orchestrator via metadata)
local journal = PANDOC_WRITER_OPTIONS.variables.journal or "ieee"
local style_map = {}

-- Load style configuration from metadata
function Meta(meta)
  if meta.journal_style then
    for k, v in pairs(meta.journal_style) do
      if type(v) == "table" and v.t == "MetaString" then
        style_map[k] = v[1]
      elseif type(v) == "table" and v.t == "MetaInlines" then
        style_map[k] = pandoc.utils.stringify(v)
      else
        style_map[k] = tostring(v)
      end
    end
  end
  return meta
end

-- ── Heading Transformation ─────────────────────────────────────────

function Header(elem)
  -- Apply journal-specific heading styles
  if elem.level == 1 then
    elem.classes:insert("section-heading-1")
    -- IEEE: uppercase section titles
    if journal:find("ieee") then
      elem.content = pandoc.List:new(
        pandoc.Str(pandoc.utils.stringify(elem.content):upper())
      )
    end
  elseif elem.level == 2 then
    elem.classes:insert("section-heading-2")
  elseif elem.level == 3 then
    elem.classes:insert("section-heading-3")
  end
  return elem
end

-- ── Paragraph Transformation ──────────────────────────────────────

function Para(elem)
  -- Check for small-caps markup
  for _, inline in ipairs(elem.content) do
    if inline.t == "Span" and inline.classes:includes("smallcaps") then
      -- Convert to LaTeX small caps in output
      inline.attributes["custom-style"] = "SmallCaps"
    end
    if inline.t == "Span" and inline.classes:includes("center") then
      inline.attributes["custom-style"] = "Centered"
    end
  end
  return elem
end

-- ── Citation Transformation ────────────────────────────────────────

function Cite(elem)
  -- Apply journal-specific citation formatting
  if journal == "nature" then
    -- Nature uses superscript citations
    for _, citation in ipairs(elem.citations) do
      citation.mode = "SuppressAuthor"
    end
  end
  return elem
end

-- ── Math/Equation Transformation ───────────────────────────────────

function Math(elem)
  -- Ensure consistent equation formatting
  if elem.mathtype == "DisplayMath" then
    -- Add journal-specific equation environment wrapping
    local text = elem.text
    -- Normalize aligned environments
    text = text:gsub("\\begin{align}", "\\begin{aligned}")
    text = text:gsub("\\end{align}", "\\end{aligned}")
    text = text:gsub("\\begin{gather}", "\\begin{gathered}")
    text = text:gsub("\\end{gather}", "\\end{gathered}")
    elem.text = text
  end
  return elem
end

-- ── Figure Transformation ──────────────────────────────────────────

function Image(elem)
  elem.attributes["custom-style"] = "Figure"
  -- Ensure figures have proper alt text
  if #elem.caption == 0 then
    elem.caption = pandoc.List:new(pandoc.Str("Figure"))
  end
  return elem
end

-- ── Table Transformation ───────────────────────────────────────────

function Table(elem)
  -- Apply journal table styling
  elem.classes:insert("journal-table")
  if journal:find("ieee") then
    -- IEEE tables: caption on top, sans-serif
    elem.attributes["caption-position"] = "top"
    elem.attributes["font-family"] = "sans-serif"
    elem.attributes["font-size"] = "8pt"
  elseif journal:find("springer") then
    elem.attributes["caption-position"] = "top"
    elem.attributes["font-size"] = "9pt"
  elseif journal == "nature" then
    elem.attributes["caption-position"] = "top"
    elem.attributes["font-size"] = "8pt"
  end
  return elem
end

-- ── Block Quote Transformation ─────────────────────────────────────

function BlockQuote(elem)
  -- Apply journal-specific quote formatting
  elem.classes:insert("journal-quote")
  return elem
end

-- ── Raw Block Transformation ───────────────────────────────────────

function RawBlock(elem)
  -- Pass through LaTeX commands in LaTeX output
  if elem.format == "tex" then
    return elem
  end
  return elem
end

-- ── Link Transformation ────────────────────────────────────────────

function Link(elem)
  -- Ensure URLs are properly formatted
  if elem.target:match("^https?://") then
    elem.classes:insert("external-link")
  end
  return elem
end

-- ── Span Transformation ────────────────────────────────────────────

function Span(elem)
  -- Handle custom style spans
  if elem.classes:includes("smallcaps") then
    elem.attributes["font-variant"] = "small-caps"
  end
  if elem.classes:includes("emphasis") then
    elem.classes:insert("Emphasis")
  end
  return elem
end

-- ── Code Block Transformation ──────────────────────────────────────

function CodeBlock(elem)
  elem.classes:insert("source-code")
  return elem
end
