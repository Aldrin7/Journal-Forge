-- PaperForge — Lua Filter: springer.lua
-- Springer Nature-specific AST transformations.

function Header(elem)
  if elem.level == 1 then
    elem.classes:insert("springer-section")
  elseif elem.level == 2 then
    elem.classes:insert("springer-subsection")
  elseif elem.level == 3 then
    -- Springer: bold italic for level 3
    elem.classes:insert("springer-subsubsection")
    for _, inline in ipairs(elem.content) do
      if inline.t == "Str" then
        -- Style handled by template, just mark class
      end
    end
  end
  return elem
end

function Math(elem)
  if elem.mathtype == "DisplayMath" then
    -- Springer: clean equation formatting
    local text = elem.text
    text = text:gsub("\\begin{align}", "\\begin{aligned}")
    text = text:gsub("\\end{align}", "\\end{aligned}")
    elem.text = text
  end
  return elem
end

function Table(elem)
  elem.classes:insert("springer-table")
  elem.attributes["caption-position"] = "top"
  elem.attributes["font-size"] = "9pt"
  return elem
end

function Cite(elem)
  -- Springer: numbered references in square brackets
  for _, citation in ipairs(elem.citations) do
    citation.mode = "NormalCitation"
  end
  return elem
end
