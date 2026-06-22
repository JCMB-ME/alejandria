/**
 * Type definitions matching the backend Pydantic schemas.
 */

export type UserRole = 'admin' | 'user' | 'guest';

export interface User {
  id: number;
  username: string;
  email: string | null;
  display_name: string | null;
  role: UserRole;
  is_active: boolean;
  can_download: boolean;
  can_edit_metadata: boolean;
  is_anonymous: boolean;
  locale: string;
  timezone: string;
  avatar_url: string | null;
  kindle_email: string | null;
  reader_theme: 'light' | 'dark' | 'sepia';
  reader_font_size: number;
  reader_line_height: number;
  reader_font_family: string;
  created_at: string;
  last_login_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
  user: User;
  csrf_token: string;
}

export interface BookAuthor {
  id: number;
  name: string;
  sort: string | null;
}

export interface TagInfo {
  id: number;
  name: string;
}

export interface SeriesInfo {
  id: number;
  name: string;
  sort: string | null;
}

export interface BookFormat {
  fmt: string;
  path: string;
  size: number;
  mtime: string | null;
}

export interface BookSummary {
  id: number;
  title: string;
  sort_title: string | null;
  authors: BookAuthor[];
  tags: TagInfo[];
  series: SeriesInfo | null;
  series_index: number | null;
  languages: string[];
  pubdate: string | null;
  publisher: string | null;
  rating: number | null;
  cover_path: string | null;
  has_cover: boolean;
  formats: BookFormat[];
}

export interface BookDetail extends BookSummary {
  description: string | null;
  comments: string | null;
  identifiers: Record<string, string>;
  timestamp: string | null;
  last_modified: string | null;
  user_progress?: number | null;
  user_finished?: boolean | null;
  on_shelves?: number[];
}

export interface BookListResponse {
  items: BookSummary[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface LibraryStats {
  total_books: number;
  total_authors: number;
  total_tags: number;
  total_series: number;
  total_size_bytes: number;
  formats: Record<string, number>;
  last_scan: string | null;
}

export interface ProgressUpdate {
  book_id: number;
  position: string;
  position_type: 'cfi' | 'page' | 'loc';
  progress_pct: number;
  device_type?: string;
  device_name?: string;
  reading_time_seconds?: number;
}

export interface ProgressRead {
  book_id: number;
  position: string;
  position_type: string;
  progress_pct: number;
  last_read_at: string;
  started_at: string | null;
  finished_at: string | null;
  total_reading_time: number;
  device_type: string | null;
  device_name: string | null;
}

export interface Shelf {
  id: number;
  user_id: number;
  name: string;
  slug: string;
  description: string | null;
  icon: string | null;
  color: string | null;
  is_public: boolean;
  shelf_type: 'manual' | 'reading' | 'finished' | 'wishlist' | 'favorites' | 'custom';
  sort_order: number;
  book_count: number;
  created_at: string;
  updated_at: string;
}

export interface Highlight {
  id: number;
  user_id: number;
  book_id: number;
  cfi: string;
  text: string;
  color: string;
  style: string;
  chapter: string | null;
  page: number | null;
  created_at: string;
  updated_at: string;
}

export interface Annotation {
  id: number;
  user_id: number;
  book_id: number;
  highlight_id: number | null;
  cfi: string | null;
  page: number | null;
  content: string;
  is_private: boolean;
  created_at: string;
  updated_at: string;
}

// --- Web scraper ---

export type ScrapeJobStatus =
  | 'queued' | 'scraping' | 'packaging' | 'done' | 'failed' | 'cancelled';

export type ScrapeFormat = 'PDF' | 'EPUB' | 'CBZ';
export type ScrapeDestination = 'library' | 'download';

export interface ScrapeJob {
  id: number;
  url: string;
  title: string | null;
  adapter_name: string;
  formats: ScrapeFormat[];
  destinations: ScrapeDestination[];
  status: ScrapeJobStatus;
  total_pages: number;
  current_page: number;
  progress_pct: number;
  total_bytes: number;
  error: string | null;
  output_paths: Record<string, string> | null;
  imported_book_ids: Record<string, number> | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ScrapeJobCreate {
  url: string;
  formats: ScrapeFormat[];
  destinations: ScrapeDestination[];
  adapter_name?: string;
  title?: string;
}

export interface AdapterImageCandidate {
  url: string;
  width: number;
  height: number;
}

export interface AdapterNextCandidate {
  selector: string;
  href: string | null;
  text: string | null;
}

export interface AdapterTestResult {
  image_candidates: AdapterImageCandidate[];
  next_candidates: AdapterNextCandidate[];
  adapter_used: string;
}
