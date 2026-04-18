-- PaperForge — Lua Filter: wiley.lua
-- Wiley-specific AST transformations.

function Header(elem)
  if elem.level == 1 then
    elem.classes:insert("wiley-section")
  elseif elem.level == 2 then
    elem.classes:insert("wiley-subsection")
  elseif elem.level == 3 then
    elem.classes:insert("wiley-subsubsection")
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
  elem.classes:insert("wiley-table")
  elem.attributes["caption-position"] = "top"
  return elem
end
