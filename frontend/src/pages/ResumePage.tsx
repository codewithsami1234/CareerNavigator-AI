import { useState } from "react"
import { analyzeResume, pipelineProblem } from "../api"
import { ResumeDetails } from "../components/views"
import { Alert, Button, Card, ProgressIndicator, Skeleton, UploadZone } from "../components/ui"
import { sampleResumeFile } from "../demo"
import { fileTooLarge } from "../evidence"
import { useWorkspace } from "../workspace"

const ACCEPT = [
  ".pdf",
  ".docx",
  ".txt",
  ".png",
  ".jpg",
  ".jpeg",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
  "image/png",
  "image/jpeg",
].join(",")

const DOCUMENT_EXTENSIONS = [".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"]
const IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg"]

const MIME_BY_EXTENSION: Record<string, string[]> = {
  ".pdf": ["application/pdf"],
  ".docx": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"],
  ".txt": ["text/plain", "text/txt"],
  ".png": ["image/png"],
  ".jpg": ["image/jpeg", "image/jpg"],
  ".jpeg": ["image/jpeg", "image/jpg"],
}

function extension(name: string) {
  const dot = name.lastIndexOf(".")
  return dot >= 0 ? name.slice(dot).toLowerCase() : ""
}

function mimeMatches(file: File, suffix: string) {
  const media = file.type.split(";", 1)[0].trim().toLowerCase()
  if (!media || media === "application/octet-stream") return true
  return (MIME_BY_EXTENSION[suffix] ?? []).includes(media)
}

export function ResumePage() {
  const { resume, useOcr, setUseOcr, setResume, clearResume, clearAll } = useWorkspace()
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  function choose(next: File | null) {
    if (!next) return
    const suffix = extension(next.name)
    if (!DOCUMENT_EXTENSIONS.includes(suffix)) {
      setFile(null)
      setError(`Unsupported file type '${suffix || "(none)"}'. Supported types: .docx, .jpeg, .jpg, .pdf, .png, .txt.`)
      return
    }
    if (!mimeMatches(next, suffix)) {
      setFile(null)
      setError("The uploaded content type does not match the file extension.")
      return
    }
    const tooLarge = fileTooLarge(next)
    if (tooLarge) {
      setFile(null)
      setError(tooLarge)
      return
    }
    setFile(next)
    setError(null)
    if (IMAGE_EXTENSIONS.includes(suffix)) {
      setUseOcr(true)
      setNotice("Photograph or image selected. OCR is on because an image has no text layer. Local Tesseract reads it when you analyze.")
      return
    }
    setNotice(null)
  }

  async function loadSample(path: string, name: string, type: string, notice: string, ocr = false) {
    setError(null)
    try {
      const response = await fetch(path)
      if (!response.ok) throw new Error("missing")
      const blob = await response.blob()
      const file = new File([blob], name, { type: blob.type || type })
      choose(file)
      if (ocr) setUseOcr(true)
      setNotice(notice)
    } catch {
      setError(`The sample ${name} could not be loaded from this app.`)
    }
  }

  async function onAnalyze() {
    if (!file) {
      setError("Choose a PDF, DOCX, TXT, PNG, or JPEG resume first.")
      return
    }
    setLoading(true)
    setError(null)
    setNotice(null)
    try {
      const analysis = await analyzeResume(file, useOcr)
      setResume(analysis)
      const problem = pipelineProblem(analysis)
      if (analysis.status === "needs_ocr") {
        const image = IMAGE_EXTENSIONS.includes(extension(file.name))
        setNotice(
          image
            ? "This image was not read because OCR is off. Turn on OCR and analyze again. OCR uses local Tesseract."
            : "This PDF did not contain enough native text. Turn on OCR and analyze again. OCR uses local Tesseract and runs only when you ask for it.",
        )
      } else if (problem) {
        setError(problem)
      } else {
        setNotice("Reading complete. Skills and sections below are extracted text, not verified facts.")
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The resume could not be analyzed.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="text-lg font-semibold">Upload a resume</h2>
        <p className="muted mt-1 text-sm leading-6">
          The file is parsed and then deleted. It is not stored. OCR is for scanned PDFs and photographs.
        </p>
        <UploadZone
          className="mt-4"
          active={dragOver}
          onDragOver={(event) => {
            event.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(event) => {
            event.preventDefault()
            setDragOver(false)
            choose(event.dataTransfer.files?.[0] ?? null)
          }}
        >
          <i className="bi bi-cloud-arrow-up icon-gold text-2xl" aria-hidden="true" />
          <p className="mt-2 text-sm font-medium">Drag a resume here</p>
          <p className="muted mt-1 text-sm">PDF, DOCX, TXT, PNG, or JPEG · up to 10 MB</p>
          <label className="btn btn-secondary mt-4 cursor-pointer">
            Browse files
            <input
              className="sr-only"
              type="file"
              accept={ACCEPT}
              onChange={(event) => choose(event.target.files?.[0] ?? null)}
            />
          </label>
          {file ? <p className="muted mt-3 text-sm">Selected: {file.name}</p> : null}
        </UploadZone>
        <label className="mt-4 flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1" checked={useOcr} onChange={(event) => setUseOcr(event.target.checked)} />
          <span>Use OCR for scanned PDFs and photographed resumes (PNG or JPEG). Leave this off for text-based PDFs. A scan or image without OCR returns needs_ocr and is not read.</span>
        </label>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={() => void onAnalyze()} disabled={loading}>{loading ? "Reading the resume…" : "Analyze resume"}</Button>
          <Button
            variant="secondary"
            onClick={() => {
              choose(sampleResumeFile())
              setNotice("Synthetic sample selected. Choose Analyze resume to send it to the local pipeline.")
            }}
          >
            Use synthetic sample
          </Button>
          <Button variant="secondary" onClick={() => void loadSample("/samples/alex-morgan-synthetic.pdf", "alex-morgan-synthetic.pdf", "application/pdf", "Synthetic PDF selected. It is the fictional Alex Morgan fixture. Choose Analyze resume to send it.")}>Use synthetic PDF</Button>
          <Button variant="secondary" onClick={() => void loadSample("/samples/alex-morgan-synthetic.docx", "alex-morgan-synthetic.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Synthetic DOCX selected. It is the fictional Alex Morgan fixture. Choose Analyze resume to send it.")}>Use synthetic DOCX</Button>
          <Button variant="secondary" onClick={() => void loadSample("/samples/alex-morgan-synthetic-scan.pdf", "alex-morgan-synthetic-scan.pdf", "application/pdf", "Synthetic scanned PDF selected. OCR is on. It is a rendered image of the fictional Alex Morgan fixture, not a photographed scan of a real resume.", true)}>Use synthetic scan</Button>
          <Button variant="secondary" onClick={() => void loadSample("/samples/alex-morgan-synthetic.png", "alex-morgan-synthetic.png", "image/png", "Synthetic photograph selected. OCR is on. It is a rendered page image of the fictional Alex Morgan fixture, not a camera photo of a real resume.", true)}>Use synthetic photograph</Button>
          {error && file ? <Button variant="ghost" onClick={() => void onAnalyze()}>Retry</Button> : null}
          <Button
            variant="ghost"
            onClick={() => {
              clearResume()
              setFile(null)
              setError(null)
              setNotice("The stored resume was cleared. Job text you typed on the matcher is unchanged until you compare again.")
            }}
          >
            Analyze another resume
          </Button>
        </div>
      </Card>
      {error ? <Alert tone="error">{error}</Alert> : null}
      {notice ? <Alert tone={notice.startsWith("This PDF") ? "warning" : "success"}>{notice}</Alert> : null}
      {loading ? (
        <div className="space-y-3">
          <ProgressIndicator label="Reading the resume locally…" />
          <Skeleton />
        </div>
      ) : null}
      {!loading && resume ? <ResumeDetails resume={resume} /> : null}
      <Card>
        <h2 className="font-semibold">Saved analysis</h2>
        <p className="muted mt-2 text-sm leading-6">The latest result stays with your account. The resume file does not.</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {confirmDelete ? (
            <>
              <Button variant="danger" onClick={() => { clearAll(); setConfirmDelete(false); setFile(null) }}>Confirm delete</Button>
              <Button variant="ghost" onClick={() => setConfirmDelete(false)}>Cancel</Button>
            </>
          ) : (
            <Button variant="danger" onClick={() => setConfirmDelete(true)}>Delete saved analysis</Button>
          )}
        </div>
      </Card>
    </div>
  )
}
