-- PaperForge — Lua Filter: elsevier.lua
-- Elsevier-specific AST transformations.

function Header(elem)
  if elem.level == 1 then
    elem.classes:insert("elsevier-section")
  elseif elem.level == 2 then
    elem.classes:insert("elsevier-subsection")
  elseif elem.level == 3 then
    elem.classes:insert("elsevier-subsubsection")
  end
  return elem
end

function Math(elem)
  if elem.mathtype == "DisplayMath" then
    local text = elem.text
    text = text:gsub("\\begin{align}", "\\begin{aligned}")
    text = text:gsub("\\end{align}", "\\end{aligned}")
    elem.text = text
  end
  return elem
end

function Table(elem)
  elem.classes:insert("elsevier-table")
  elem.attributes["caption-position"] = "top"
  return elem
end

function Cite(elem)
  -- Elsevier: numbered references
  for _, citation in ipairs(elem.citations) do
    citation.mode = "NormalCitation"
  end
  return elem
end
