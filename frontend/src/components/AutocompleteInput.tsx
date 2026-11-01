import { useId, useState } from 'react'

interface Props {
  value: string
  onChange: (value: string) => void
  suggestions: string[]
  multiple?: boolean
  placeholder?: string
}

export function AutocompleteInput({ value, onChange, suggestions, multiple = false, placeholder }: Props) {
  const listId = useId()
  const [focused, setFocused] = useState(false)
  const [active, setActive] = useState(0)
  const separator = multiple ? value.lastIndexOf(',') + 1 : 0
  const query = value.slice(separator).trimStart()
  const selected = multiple ? new Set(value.slice(0, separator).split(',').map((tag) => tag.trim().toLocaleLowerCase())) : new Set<string>()
  const unique = [...new Map(suggestions.map((suggestion) => [suggestion.toLocaleLowerCase(), suggestion])).values()]
  const matches = query ? unique.filter((suggestion) =>
    suggestion.toLocaleLowerCase().startsWith(query.toLocaleLowerCase()) &&
    !selected.has(suggestion.toLocaleLowerCase()) &&
    suggestion.toLocaleLowerCase() !== query.toLocaleLowerCase()).slice(0, 8) : []
  const visible = focused && matches.length > 0

  const complete = (suggestion: string) => {
    onChange(multiple ? `${value.slice(0, separator)}${separator ? ' ' : ''}${suggestion}, ` : suggestion)
    setFocused(false)
    setActive(0)
  }

  return <div className="autocomplete-field">
    <input
      value={value}
      placeholder={placeholder}
      role="combobox"
      aria-autocomplete="list"
      aria-expanded={visible}
      aria-controls={visible ? listId : undefined}
      aria-activedescendant={visible ? `${listId}-${Math.min(active, matches.length - 1)}` : undefined}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
      onChange={(event) => { onChange(event.target.value); setFocused(true); setActive(0) }}
      onKeyDown={(event) => {
        if (!visible) return
        if (event.key === 'ArrowDown') { event.preventDefault(); setActive((current) => (current + 1) % matches.length) }
        if (event.key === 'ArrowUp') { event.preventDefault(); setActive((current) => (current - 1 + matches.length) % matches.length) }
        if (event.key === 'Tab' || event.key === 'Enter') { event.preventDefault(); complete(matches[Math.min(active, matches.length - 1)]) }
        if (event.key === 'Escape') { event.preventDefault(); setFocused(false) }
      }}
    />
    {visible && <ul id={listId} role="listbox" className="autocomplete-list">
      {matches.map((suggestion, index) => <li
        id={`${listId}-${index}`}
        key={suggestion}
        role="option"
        aria-selected={index === active}
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => complete(suggestion)}
      >{suggestion}</li>)}
    </ul>}
  </div>
}
