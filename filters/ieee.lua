-- PaperForge — Lua Filter: ieee.lua
-- IEEE-specific AST transformations.

function Header(elem)
  if elem.level == 1 then
    -- IEEE: Roman numeral section numbers, uppercase titles
    local text = pandoc.utils.stringify(elem.content)
    elem.content = pandoc.List:new(pandoc.Str(text:upper()))
    elem.classes:insert("ieee-section")
  elseif elem.level == 2 then
    elem.classes:insert("ieee-subsection")
  elseif elem.level == 3 then
    elem.classes:insert("ieee-subsubsection")
  end
  return elem
end

function Math(elem)
  -- IEEE: equations numbered on the right
  if elem.mathtype == "DisplayMath" then
    elem.attributes["class"] = "ieee-equation"
  end
  return elem
end

function Table(elem)
  -- IEEE: sans-serif tables, 8pt font, caption on top
  elem.classes:insert("ieee-table")
  elem.attributes["caption-position"] = "top"
  elem.attributes["font-family"] = "sans-serif"
  elem.attributes["font-size"] = "8pt"
  return elem
end

function Cite(elem)
  -- IEEE: numbered references [1], [2], etc.
  for _, citation in ipairs(elem.citations) do
    citation.mode = "NormalCitation"
  end
  return elem
end

function Image(elem)
  -- IEEE: figures with caption below
  elem.attributes["caption-position"] = "bottom"
  return elem
end
