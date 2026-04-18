-- PaperForge — Lua Filter: acm.lua
-- ACM-specific AST transformations.

function Header(elem)
  if elem.level == 1 then
    elem.classes:insert("acm-section")
  elseif elem.level == 2 then
    elem.classes:insert("acm-subsection")
  elseif elem.level == 3 then
    elem.classes:insert("acm-subsubsection")
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
  elem.classes:insert("acm-table")
  elem.attributes["caption-position"] = "top"
  elem.attributes["font-size"] = "9pt"
  return elem
end

function CodeBlock(elem)
  -- ACM: use acmart's code environment
  elem.classes:insert("acm-code")
  return elem
end
