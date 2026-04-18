-- PaperForge — Lua Filter: nature.lua
-- Nature-specific AST transformations.

function Header(elem)
  if elem.level == 1 then
    elem.classes:insert("nature-section")
  elseif elem.level == 2 then
    elem.classes:insert("nature-subsection")
  end
  return elem
end

function Cite(elem)
  -- Nature: superscript citations
  for _, citation in ipairs(elem.citations) do
    citation.mode = "SuppressAuthor"
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
  elem.classes:insert("nature-table")
  elem.attributes["caption-position"] = "top"
  elem.attributes["font-size"] = "8pt"
  return elem
end
