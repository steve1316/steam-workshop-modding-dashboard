/** Props for DownloadProgress. */
interface DownloadProgressProps {
    completed: number
    /** Total bytes. Must be greater than 0. */
    total: number
}

/**
 * Progress bar for a download or install, with a "50% (512 / 1024 MB)" line under it.
 *
 * @param completed Bytes done.
 * @param total Total bytes.
 * @returns The progress bar and its text.
 */
export default function DownloadProgress({ completed, total }: DownloadProgressProps) {
    const percent = Math.round((completed / total) * 100)
    return (
        <div>
            <div className="progress-bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
                <div className="progress-bar-fill" style={{ width: `${percent}%` }} />
            </div>
            <div className="download-progress-text">
                {percent}% ({Math.round(completed / 1024 / 1024)} / {Math.round(total / 1024 / 1024)} MB)
            </div>
        </div>
    )
}
