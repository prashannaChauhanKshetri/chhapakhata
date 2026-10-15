/**
 * PDF and Excel downloads. PDFs open in a new tab, ready for the print
 * dialog; spreadsheets are saved with the server's filename.
 */
import { ensureCsrfCookie } from './client';
import { ApiError } from './errors';

interface FileOptions {
  method?: 'GET' | 'POST';
  /** Force a download even for PDFs. */
  download?: boolean;
}

function filenameFrom(response: Response, fallback: string): string {
  const disposition = response.headers.get('Content-Disposition') ?? '';
  const match = /filename="?([^";]+)"?/i.exec(disposition);
  return match?.[1] ?? fallback;
}

export async function openFile(url: string, options: FileOptions = {}): Promise<void> {
  const method = options.method ?? 'GET';
  // Open the tab synchronously (before awaiting) so pop-up blockers allow it.
  const isPdfView = !options.download;
  const tab = isPdfView ? window.open('', '_blank') : null;
  try {
    const headers: Record<string, string> = {};
    if (method !== 'GET') headers['X-CSRFToken'] = await ensureCsrfCookie();
    const response = await fetch(url, { method, headers, credentials: 'same-origin' });
    if (!response.ok) throw await ApiError.fromResponse(response);
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const isPdf = blob.type === 'application/pdf';
    if (tab && isPdf) {
      tab.location.href = objectUrl;
    } else {
      tab?.close();
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = filenameFrom(response, 'download');
      document.body.appendChild(link);
      link.click();
      link.remove();
    }
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
  } catch (error) {
    tab?.close();
    throw error instanceof ApiError ? error : new ApiError(0, []);
  }
}
