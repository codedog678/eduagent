import { useCallback, useEffect, useRef, useState } from 'react'

export interface AgentEvent {
  event_type: string
  source: string
  data: Record<string, unknown>
  timestamp: string
  correlation_id?: string | null
}

function interactionKey(event: AgentEvent): string {
  return event.correlation_id || `${event.timestamp}-${event.event_type}`
}

function eventKey(event: AgentEvent): string {
  return `${event.timestamp}-${event.source}-${event.event_type}`
}

export function useWebSocket(learnerId: string) {
  const [eventGroups, setEventGroups] = useState<AgentEvent[][]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef(0)

  const appendInteraction = useCallback((events: AgentEvent[]) => {
    if (!events.length) return
    const key = interactionKey(events[0])
    setEventGroups((prev) => {
      const next = [...prev]
      const matchIndex = next.findIndex((group) => group.length > 0 && interactionKey(group[0]) === key)
      if (matchIndex >= 0) {
        next.splice(matchIndex, 1)
      }
      return [events, ...next].slice(0, 20)
    })
  }, [])

  const appendEvent = useCallback((event: AgentEvent) => {
    const key = interactionKey(event)
    setEventGroups((prev) => {
      const next = [...prev]
      const matchIndex = next.findIndex((group) => group.length > 0 && interactionKey(group[0]) === key)
      if (matchIndex >= 0) {
        if (next[matchIndex].some((item) => eventKey(item) === eventKey(event))) {
          return next
        }
        const updatedGroup = [...next[matchIndex], event]
        next.splice(matchIndex, 1)
        next.unshift(updatedGroup)
        return next.slice(0, 20)
      }
      return [[event], ...next].slice(0, 20)
    })
  }, [])

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/${learnerId}`)

    ws.onopen = () => {
      setConnected(true)
      retryRef.current = 0
    }

    ws.onmessage = (message) => {
      const event: AgentEvent = JSON.parse(message.data)
      appendEvent(event)
    }

    ws.onclose = () => {
      setConnected(false)
      const delay = Math.min(1000 * 2 ** retryRef.current, 30000)
      retryRef.current += 1
      window.setTimeout(connect, delay)
    }

    ws.onerror = () => ws.close()
    wsRef.current = ws
  }, [appendEvent, learnerId])

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [connect])

  const send = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  const events = eventGroups.flat()

  return { events, eventGroups, connected, send, appendInteraction }
}
