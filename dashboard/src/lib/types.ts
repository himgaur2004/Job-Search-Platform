export interface SummaryData {
  sent_today: number;
  replies: number;
  interviews: number;
  success_rate: number;
}

export interface Job {
  id: number;
  company: string;
  title: string;
  location: string | null;
  url: string;
  jd_text: string | null;
  source: string | null;
  match_score: number | null;
  created_at: string;
  recruiter_email?: string;
  status?: string;
  stage?: string;
  apply_error?: string;
}

export interface Reply {
  id: number;
  email_id: number;
  raw_text: string;
  category: string;
  confidence: number;
  received_at: string;
  recruiter_email?: string;
}

export interface Followup {
  id: number;
  recruiter_email: string;
  sent_at: string;
  company: string;
  days_since_sent: number;
}

export interface Template {
  id: number;
  name: string;
  subject_template: string;
  body_template: string;
  is_active: boolean;
  created_at: string;
}
