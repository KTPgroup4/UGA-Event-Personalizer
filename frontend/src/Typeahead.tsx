import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react"

// One suggestion. `group` is the category or college it belongs to, shown in grey beside it.
export type SuggestionItem = {
  id: string
  name: string
  group: string
  strong?: boolean // an "All Music events" row: shown first when the box is empty
}

type Props = {
  label: string // read out by screen readers
  placeholder: string
  items: SuggestionItem[]
  selected: string[]
  onToggle: (id: string) => void
  isDisabled?: (id: string) => boolean // for example "you already picked the most allowed"
  closeOnPick?: boolean // empty and close the box after a pick (good when you only pick one or two)
  emptyHint?: string
}

const MAX_SUGGESTIONS = 60

// Lower case, no accents, punctuation turned into spaces: "Law, Government & Policy" -> "law government policy"
function normalize(text: string) {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
}

type Prepared = SuggestionItem & { nameWords: string[]; groupWords: string[] }

function startsAWord(words: string[], token: string) {
  return words.some(word => word.startsWith(token))
}

export default function Typeahead({
  label,
  placeholder,
  items,
  selected,
  onToggle,
  isDisabled,
  closeOnPick = false,
  emptyHint = "Nothing matches. Try a shorter word.",
}: Props) {
  const baseId = useId()
  const listId = `${baseId}-list`
  const [query, setQuery] = useState("")
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const listRef = useRef<HTMLDivElement>(null)

  const prepared = useMemo<Prepared[]>(
    () =>
      items.map(item => ({
        ...item,
        nameWords: normalize(item.name).split(" "),
        groupWords: normalize(item.group).split(" "),
      })),
    [items]
  )

  const tokens = normalize(query).split(" ").filter(Boolean)

  // Suggestions: every typed word must start a word in the name or the group.
  const shown = useMemo(() => {
    if (tokens.length === 0) {
      // Nothing typed yet: offer the "All ... events" rows if there are any, otherwise everything.
      const browse = prepared.filter(item => item.strong)
      return browse.length > 0 ? browse : prepared
    }
    const found = prepared.filter(item =>
      tokens.every(token => startsAWord(item.nameWords, token) || startsAWord(item.groupWords, token))
    )
    // Best matches first: 0 = the name starts with what you typed, 1 = a later word in the name does,
    // 2 = only the category or college name matches. (An "All Music events" row counts as "Music".)
    const rank = (item: Prepared) => {
      const lead = item.strong ? item.groupWords : item.nameWords
      if (lead[0].startsWith(tokens[0]) && tokens.every(token => startsAWord(item.nameWords, token) || startsAWord(item.groupWords, token))) return 0
      if (tokens.every(token => startsAWord(item.nameWords, token))) return 1
      return 2
    }
    // Among the best matches, the shortest first word wins: "Music" before "Museum", "Biology" before "Biological".
    const lead = (item: Prepared) => (item.strong ? item.groupWords : item.nameWords)[0].length
    return found
      .map((item, order) => ({ item, order, score: rank(item) }))
      .sort((a, b) => a.score - b.score || (a.score === 0 ? lead(a.item) - lead(b.item) : 0) || a.order - b.order)
      .map(entry => entry.item)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prepared, query])

  const visible = shown.slice(0, MAX_SUGGESTIONS)

  useEffect(() => {
    setActive(0)
    listRef.current?.scrollTo({ top: 0 })
  }, [query])

  function scrollToRow(index: number) {
    listRef.current?.querySelector<HTMLElement>(`[data-index="${index}"]`)?.scrollIntoView({ block: "nearest" })
  }

  function move(delta: number) {
    if (!open) {
      setOpen(true)
      return
    }
    if (visible.length === 0) return
    const next = (active + delta + visible.length) % visible.length
    setActive(next)
    scrollToRow(next)
  }

  function pick(item: Prepared) {
    const isPicked = selected.includes(item.id)
    if (!isPicked && isDisabled?.(item.id)) return
    onToggle(item.id)
    if (closeOnPick && !isPicked) {
      setQuery("")
      setOpen(false)
    }
  }

  function handleKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault()
      move(1)
    } else if (event.key === "ArrowUp") {
      event.preventDefault()
      move(-1)
    } else if (event.key === "Enter") {
      event.preventDefault() // Enter picks the highlighted suggestion and never submits anything
      if (open && visible[active]) pick(visible[active])
    } else if (event.key === "Escape") {
      event.preventDefault()
      if (open) setOpen(false)
      else setQuery("")
    }
  }

  const optionId = (index: number) => `${baseId}-option-${index}`

  return (
    <div className="typeahead">
      <input
        type="text"
        role="combobox"
        aria-label={label}
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={open && visible.length > 0 ? optionId(active) : undefined}
        autoComplete="off"
        spellCheck={false}
        placeholder={placeholder}
        value={query}
        onChange={event => {
          setQuery(event.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onClick={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={handleKey}
      />

      {open && (
        <div className="typeahead-list" id={listId} role="listbox" aria-label={label} aria-multiselectable="true" ref={listRef}>
          {tokens.length === 0 && (
            <div className="typeahead-note">Start typing, or pick a category</div>
          )}

          {visible.length === 0 && (
            <div className="typeahead-empty">
              {items.length === 0
                ? "The list hasn't loaded. Make sure the backend is running, then refresh the page."
                : emptyHint}
            </div>
          )}

          {visible.map((item, index) => {
            const isSelected = selected.includes(item.id)
            const blocked = !isSelected && !!isDisabled?.(item.id)
            return (
              <div
                key={`${item.group}|${item.id}`}
                id={optionId(index)}
                data-index={index}
                role="option"
                aria-selected={isSelected}
                aria-disabled={blocked || undefined}
                className={
                  "typeahead-row" +
                  (isSelected ? " selected" : "") +
                  (index === active ? " active" : "") +
                  (blocked ? " blocked" : "")
                }
                onMouseDown={event => event.preventDefault()} // keep the cursor in the box
                onMouseMove={() => setActive(index)}
                onClick={() => pick(item)}
              >
                <span className="typeahead-check" aria-hidden="true">{isSelected ? "✓" : ""}</span>
                <span className="typeahead-name">{item.name}</span>
                {!(tokens.length === 0 && item.strong) && <span className="typeahead-group">{item.group}</span>}
              </div>
            )
          })}

          {shown.length > MAX_SUGGESTIONS && (
            <div className="typeahead-note">Showing the first {MAX_SUGGESTIONS}. Keep typing to narrow it down.</div>
          )}
        </div>
      )}
    </div>
  )
}
