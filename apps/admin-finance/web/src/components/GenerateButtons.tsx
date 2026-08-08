import { useState } from 'react'
import { api } from '../lib/api'
import { useToast } from './ui'
import { Icon } from './icons'

type Kind = 'timesheet' | 'invoice' | 'expense'

/** Generate a PDF / Word document on the server, then trigger a download of the stored file. */
export function GenerateButtons({
  kind,
  refId,
  disabled,
  disabledHint,
  onGenerated,
}: {
  kind: Kind
  refId: string
  disabled?: boolean
  disabledHint?: string
  onGenerated?: () => void
}) {
  const notify = useToast()
  const [busy, setBusy] = useState<'pdf' | 'docx' | null>(null)

  const run = async (format: 'pdf' | 'docx') => {
    setBusy(format)
    try {
      const doc = await api.generate(kind, refId, format)
      notify('ok', `${format.toUpperCase()} generated`)
      const a = document.createElement('a')
      a.href = api.downloadUrl(doc.id, doc.filename)
      a.download = doc.filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      onGenerated?.()
    } catch (e) {
      notify('err', String(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="flex items-center gap-2" title={disabled ? disabledHint : undefined}>
      <button className="btn-ghost btn-sm" onClick={() => run('pdf')} disabled={disabled || busy !== null}>
        <Icon name="download" className="h-3.5 w-3.5 text-ink-400" />
        {busy === 'pdf' ? '…' : 'PDF'}
      </button>
      <button className="btn-ghost btn-sm" onClick={() => run('docx')} disabled={disabled || busy !== null}>
        <Icon name="download" className="h-3.5 w-3.5 text-ink-400" />
        {busy === 'docx' ? '…' : 'Word'}
      </button>
    </div>
  )
}
