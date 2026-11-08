
/**
 * SitePilot backend API adapter.
 * Buyer tokens are stored in sessionStorage for the current demo.
 */

export type ApiProject = {
  id: string;
  name: string;
  city: string;
  description: string;
  price_min_inr: number;
  price_max_inr: number;
  rera_registration: string | null;
  cover_image_url?: string | null;
};

export type ApiSlot = {
  slot_id: string;
  starts_at: string;
  ends_at: string;
  available: boolean;
};

export type ApiSlotList = {
  project_id: string;
  date: string;
  timezone: string;
  slots: ApiSlot[];
};

export type ApiBooking = {
  booking_id: string;
  status: string;
  project_id: string;
  slot_id: string;
  starts_at: string;
  ends_at: string;
  reminder_status: string;
};

export const backendProjectId = (uiId: string) =>
  uiId === 'aranya'
    ? 'project-1'
    : uiId === 'vista'
      ? 'project-2'
      : uiId;

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
).replace(/\/$/, '');

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string
  ) {
    super(detail);
    this.name = 'ApiError';
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE}/api/v1${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new ApiError(
      0,
      'Cannot connect to the SitePilot API. Check that FastAPI is running.'
    );
  }

  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail =
      typeof body.detail === 'string'
        ? body.detail
        : typeof body.error?.message === 'string'
          ? body.error.message
          : `Request failed (${response.status})`;

    throw new ApiError(response.status, detail);
  }

  return body as T;
}

export type PublicSalesperson = {
  id: string;
  name: string;
  role_title: string;
  phone: string;
  email: string;
};

export type ProjectFact = {
  id: string;
  project_id: string;
  key: string;
  value: string;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  reviewed_at: string | null;
};

export const sitepilotApi = {
  health: async (): Promise<{
    status: string;
    api: string;
    build?: string;
  }> => {
    const response = await fetch(`${API_BASE}/health`, {
      cache: 'no-store',
    });

    if (!response.ok) {
      throw new Error('Backend health check failed');
    }

    return response.json();
  },

  projects: () =>
    request<ApiProject[]>('/projects'),

  project: (id: string) =>
    request<ApiProject>(
      `/projects/${encodeURIComponent(id)}`
    ),

  publicSalespeople: (id: string) =>
    request<PublicSalesperson[]>(
      `/projects/${encodeURIComponent(id)}/salespeople`
    ),

  contact: () =>
    request<{
      phone: string | null;
      email: string | null;
    }>('/contact'),

  projectFacts: (id: string) =>
    request<{
      project_id: string;
      facts: ProjectFact[];
    }>(
      `/projects/${encodeURIComponent(id)}/facts`
    ),

  registerBuyer: (data: {
    name: string;
    phone: string;
    password: string;
    project_id: string;
    contact_consent: boolean;
  }) =>
    request<{
      lead_id: string;
      buyer_session_token: string;
    }>(
      '/buyer/auth/register',
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    ),

  loginBuyer: (
    phone: string,
    password: string,
    project_id: string
  ) =>
    request<{
      lead_id: string;
      buyer_session_token: string;
    }>(
      '/buyer/auth/login',
      {
        method: 'POST',
        body: JSON.stringify({
          phone,
          password,
          project_id,
        }),
      }
    ),

  claimBuyer: (
    token: string,
    password: string
  ) =>
    request<{
      lead_id: string;
      status: string;
    }>(
      '/buyer/auth/claim',
      {
        method: 'POST',
        body: JSON.stringify({ password }),
      },
      token
    ),

  createLead: (payload: {
    name: string;
    phone: string;
    project_id: string;
    source: 'website';
    contact_consent: boolean;
  }) =>
    request<{
      lead_id: string;
      buyer_session_token: string;
    }>(
      '/leads',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    ),

  slots: (
    projectId: string,
    date: string
  ) =>
    request<ApiSlotList>(
      `/projects/${encodeURIComponent(projectId)}/slots?date=${encodeURIComponent(date)}`
    ),

  book: (
    projectId: string,
    slotId: string,
    token: string,
    key: string
  ) =>
    request<ApiBooking>(
      '/buyer/bookings',
      {
        method: 'POST',
        headers: {
          'Idempotency-Key': key,
        },
        body: JSON.stringify({
          project_id: projectId,
          slot_id: slotId,
        }),
      },
      token
    ),

  bookings: (token: string) =>
    request<ApiBooking[]>(
      '/buyer/bookings',
      {},
      token
    ),

  buyerMe: (token: string) =>
    request<{
      lead_id: string;
      name: string;
      project_id: string;
      status: string;
      contact_consent: boolean;
      has_account: boolean;
    }>(
      '/buyer/me',
      {},
      token
    ),

  cancel: (
    bookingId: string,
    token: string
  ) =>
    request<ApiBooking>(
      `/buyer/bookings/${encodeURIComponent(bookingId)}/cancel`,
      { method: 'POST' },
      token
    ),
};

export const buyerSession = {
  save(projectId: string, token: string) {
    if (typeof window !== 'undefined') {
      sessionStorage.setItem(
        `sitepilot_buyer_${projectId}`,
        token
      );
    }
  },

  load(projectId: string) {
    return typeof window === 'undefined'
      ? null
      : sessionStorage.getItem(
          `sitepilot_buyer_${projectId}`
        );
  },
};

export const inr = (amount: number) =>
  `₹${new Intl.NumberFormat('en-IN').format(amount)}`;

export type ChatResult = {
  message_id: string;

  ai_status:
    | 'local_model'
    | 'local_classifier'
    | 'local_policy'
    | 'unavailable'
    | 'ticket_policy'
    | 'human_takeover';

  build?: string;
  reply: string | null;
  response_language?: 'en' | 'hi' | 'gu';
  message?: string;
  grounding_status?: string;

  reply_strategy?:
    | 'local_model_contextual'
    | 'server_controlled'
    | 'server_template_fallback'
    | 'unavailable';

  context_turns_used?: number;

  hesitation: {
    category: string;
    evidence: string;
    certainty: string;
  } | null;

  human_handoff_available: boolean;

  booking_options?: Array<{
    slot_id: string;
    project_id: string;
    starts_at: string;
    ends_at: string;
    timezone: string;
  }>;

  confirmation_required?: boolean;
};

export type BuyerTicketSummary = {
  id: string;
  reference: string;
  lead_id: string;
  status: string;

  owner: {
    name: string;
    email: string;
  } | null;

  project_ids: string[];
  requirements: Record<string, unknown>;
  contact_consent: boolean;
  buyer_phone?: string | null;
  created_at: string;
  accepted_at?: string | null;
};

export type TicketHistoryEntry = {
  type: 'message' | 'event';
  id: string;
  speaker?: string;
  kind?: string;
  text: string;
  at: string;
};

export const ticketApi = {
  current: (token: string) =>
    request<BuyerTicketSummary>(
      '/buyer/ticket',
      {},
      token
    ),

  addProject: (
    token: string,
    project_id: string
  ) =>
    request<BuyerTicketSummary>(
      '/buyer/ticket/projects',
      {
        method: 'POST',
        body: JSON.stringify({ project_id }),
      },
      token
    ),

  projectFacts: (token: string) =>
    request<{
      ticket_reference: string;
      projects: Array<{
        id: string;
        name: string;
        facts: Record<string, string>;
      }>;
    }>(
      '/buyer/ticket/projects',
      {},
      token
    ),

  download: async (token: string) => {
    const response = await fetch(
      `${API_BASE}/api/v1/buyer/ticket/export`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

    if (!response.ok) {
      throw new Error('Ticket export failed');
    }

    const body = await response.blob();
    const url = URL.createObjectURL(body);

    try {
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'SitePilot_Ticket.txt';
      anchor.click();
    } finally {
      URL.revokeObjectURL(url);
    }
  },

  queue: (token: string) =>
    request<BuyerTicketSummary[]>(
      '/sales/tickets/queue',
      {},
      token
    ),

  mine: (token: string) =>
    request<BuyerTicketSummary[]>(
      '/sales/tickets/mine',
      {},
      token
    ),

  salesDetail: (
    token: string,
    id: string
  ) =>
    request<{
      ticket: BuyerTicketSummary;
      history: TicketHistoryEntry[];
    }>(
      `/sales/tickets/${encodeURIComponent(id)}`,
      {},
      token
    ),

  accept: (
    token: string,
    id: string
  ) =>
    request<BuyerTicketSummary>(
      `/sales/tickets/${encodeURIComponent(id)}/accept`,
      { method: 'POST' },
      token
    ),

  salesMessage: (
    token: string,
    id: string,
    message: string
  ) =>
    request<unknown>(
      `/sales/tickets/${encodeURIComponent(id)}/messages`,
      {
        method: 'POST',
        body: JSON.stringify({ message }),
      },
      token
    ),

  resolve: (
    token: string,
    id: string,
    note: string
  ) =>
    request<unknown>(
      `/sales/tickets/${encodeURIComponent(id)}/resolve`,
      {
        method: 'POST',
        body: JSON.stringify({ note }),
      },
      token
    ),

  revoke: (
    token: string,
    id: string,
    reason: string
  ) =>
    request<BuyerTicketSummary>(
      `/sales/tickets/${encodeURIComponent(id)}/revoke`,
      {
        method: 'POST',
        body: JSON.stringify({ reason }),
      },
      token
    ),
};

export const chatApi = {
  send: (
    token: string,
    text: string,
    language: 'en' | 'hi' | 'gu'
  ) =>
    request<ChatResult>(
      '/buyer/conversations/messages',
      {
        method: 'POST',
        body: JSON.stringify({
          message: text,
          language,
        }),
      },
      token
    ),

  history: (token: string) =>
    request<
      Array<{
        message_id: string;
        speaker: 'buyer' | 'ai' | 'sales';
        message: string;
      }>
    >(
      '/buyer/conversations/messages',
      {},
      token
    ),

  bookingOptions: (token: string) =>
    request<{
      project_id: string;
      confirmation_required: boolean;
      slots: Array<{
        slot_id: string;
        project_id: string;
        starts_at: string;
        ends_at: string;
        timezone: string;
      }>;
    }>(
      '/buyer/assistant/booking-options',
      {},
      token
    ),

  handoff: (token: string) =>
    request<{
      status: string;
      assignment_status: string;
      message: string;
      salespeople: PublicSalesperson[];
    }>(
      '/buyer/handoff',
      {
        method: 'POST',
      },
      token
    ),

  handoffStatus: (token: string) =>
    request<{
      status: string;
      assigned: boolean;
      message: string;
      salespeople: PublicSalesperson[];
    }>(
      '/buyer/handoff',
      {},
      token
    ),

  consent: (
    token: string,
    enabled: boolean
  ) =>
    request<{
      contact_consent: boolean;
    }>(
      '/buyer/preferences',
      {
        method: 'PATCH',
        body: JSON.stringify({
          contact_consent: enabled,
        }),
      },
      token
    ),
};

export type AIReviewItem = {
  id: string;
  lead_id: string;
  project_id: string | null;
  buyer_name: string;
  contact_consent: boolean;
  source_message: string;
  reason: string;
  status: 'open' | 'reviewed';
  created_at: string;
  reviewed_at: string | null;
  review_note: string | null;
};

export type AIReviewQueue = {
  items: AIReviewItem[];
  timezone: string;
  review_policy: string;
};

export type SalesLead = {
  lead_id: string;
  name: string;
  phone?: string;
  source: string;
  project_id: string;
  status: string;
  contact_consent: boolean;
  preferred_configuration?: string | null;
  budget_max_inr?: number | null;
  assigned_user_id?: string | null;
  created_at?: string;
};

export type SalesBooking = ApiBooking & {
  lead_id: string;
  lead_name: string;
};

export type SalesMetrics = {
  leads_total: number;
  leads_this_month: number;
  booked_visits: number;
  attended_visits: number;
  handoff_pending: number;
  median_first_response_minutes: number | null;
  response_sample_size: number;
  unreplied_over_48h: number;

  sources: Array<{
    source: string;
    leads: number;
    booked: number;
    attended: number;
  }>;
};

export type SalesMessage = {
  message_id: string;
  speaker: string;
  message: string;
  created_at: string;
};

export type SalesConcern = {
  category: string;
  source_message_id: string;
  evidence: string;
  certainty: string;
};

export const salesApi = {
  login: (
    email: string,
    password: string
  ) =>
    request<{
      access_token: string;
    }>(
      '/auth/login',
      {
        method: 'POST',
        body: JSON.stringify({
          email,
          password,
        }),
      }
    ),

  acceptInvitation: (
    email: string,
    invitation_code: string,
    password: string
  ) =>
    request<{
      status: string;
      email: string;
      message: string;
    }>(
      '/auth/accept-invitation',
      {
        method: 'POST',
        body: JSON.stringify({
          email,
          invitation_code,
          password,
        }),
      }
    ),

  team: (token: string) =>
    request<
      Array<{
        id: string;
        email: string;
        display_name: string;
        role: 'sales_head' | 'sales';
      }>
    >(
      '/sales/team',
      {},
      token
    ),

  createInvitation: (
    token: string,
    email: string,
    display_name: string
  ) =>
    request<{
      email: string;
      display_name: string;
      invitation_code: string;
      expires_at: string;
      message: string;
    }>(
      '/sales/invitations',
      {
        method: 'POST',
        body: JSON.stringify({
          email,
          display_name,
        }),
      },
      token
    ),

  me: (token: string) =>
    request<{
      id: string;
      display_name: string;
      email: string;
      role: 'sales_head' | 'sales';
    }>(
      '/auth/me',
      {},
      token
    ),

  leads: (token: string) =>
    request<SalesLead[]>(
      '/sales/leads',
      {},
      token
    ),

  lead: (
    token: string,
    id: string
  ) =>
    request<SalesLead>(
      `/sales/leads/${encodeURIComponent(id)}`,
      {},
      token
    ),

  leadTicket: (
    token: string,
    id: string
  ) =>
    request<BuyerTicketSummary>(
      `/sales/leads/${encodeURIComponent(id)}/ticket`,
      {},
      token
    ),

  messages: (
    token: string,
    id: string
  ) =>
    request<SalesMessage[]>(
      `/sales/leads/${encodeURIComponent(id)}/messages`,
      {},
      token
    ),

  concerns: (
    token: string,
    id: string
  ) =>
    request<{
      barriers: SalesConcern[];
    }>(
      `/sales/leads/${encodeURIComponent(id)}/hesitation`,
      {},
      token
    ),

  handoffs: (token: string) =>
    request<SalesLead[]>(
      '/sales/handoffs',
      {},
      token
    ),

  aiReviews: (token: string) =>
    request<AIReviewQueue>(
      '/sales/ai-review',
      {},
      token
    ),

  resolveReview: (
    token: string,
    id: string,
    note: string
  ) =>
    request<{
      id: string;
      status: string;
    }>(
      `/sales/ai-review/${encodeURIComponent(id)}/review`,
      {
        method: 'POST',
        body: JSON.stringify({ note }),
      },
      token
    ),

  bookings: (token: string) =>
    request<SalesBooking[]>(
      '/sales/bookings',
      {},
      token
    ),

  dashboard: (token: string) =>
    request<SalesMetrics>(
      '/sales/dashboard/overview',
      {},
      token
    ),

  users: (token: string) =>
    request<
      Array<{
        id: string;
        display_name: string;
      }>
    >(
      '/sales/users',
      {},
      token
    ),

  assign: (
    token: string,
    id: string,
    user_id: string
  ) =>
    request<{
      assigned_user_id: string;
    }>(
      `/sales/leads/${encodeURIComponent(id)}/assign`,
      {
        method: 'PATCH',
        body: JSON.stringify({ user_id }),
      },
      token
    ),

  acceptHandoff: (
    token: string,
    id: string
  ) =>
    request<{
      status: string;
      assigned: boolean;
    }>(
      `/sales/leads/${encodeURIComponent(id)}/handoff/accept`,
      {
        method: 'POST',
      },
      token
    ),

  attendance: (
    token: string,
    id: string,
    status: 'attended' | 'no_show'
  ) =>
    request<ApiBooking>(
      `/sales/bookings/${encodeURIComponent(id)}/attendance`,
      {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      },
      token
    ),
};

export type AdminSalesperson = PublicSalesperson & {
  approved: boolean;
  active: boolean;
  updated_at: string;
};

export type AdminProjectImage = {
  id: string;
  approved: boolean;
  preview_url: string;
};

export type SalespersonForm = {
  name: string;
  role_title: string;
  phone: string;
  email: string;
  active: boolean;
};

export const absoluteMediaUrl = (
  url?: string | null
) =>
  url ? `${API_BASE}${url}` : undefined;

export type FactsAdmin = {
  project_id: string;
  is_sales_head: boolean;
  approved: ProjectFact[];
  history: ProjectFact[];
};

export type ManagedSlot = {
  slot_id: string;
  project_id: string;
  starts_at: string;
  ends_at: string;
  enabled: boolean;
};

export type ReminderRecord = {
  id: string;
  booking_id: string;
  kind: string;
  due_at: string;
  status: string;
  processed_at: string | null;
};

export type ManagedProject = ApiProject & {
  published: boolean;
};

export const adminApi = {
  projects: (token: string) =>
    request<ManagedProject[]>(
      '/sales/projects',
      {},
      token
    ),

  addProject: (
    token: string,
    data: {
      name: string;
      city: string;
      description: string;
      salesperson_name?: string;
      salesperson_role?: string;
      salesperson_phone?: string;
      salesperson_email?: string;
    }
  ) =>
    request<ManagedProject>(
      '/sales/projects',
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
      token
    ),

  salespeople: (
    token: string,
    id: string
  ) =>
    request<AdminSalesperson[]>(
      `/sales/projects/${encodeURIComponent(id)}/salespeople`,
      {},
      token
    ),

  addSalesperson: (
    token: string,
    id: string,
    payload: SalespersonForm
  ) =>
    request<AdminSalesperson>(
      `/sales/projects/${encodeURIComponent(id)}/salespeople`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      token
    ),

  editSalesperson: (
    token: string,
    id: string,
    contactId: string,
    payload: SalespersonForm
  ) =>
    request<AdminSalesperson>(
      `/sales/projects/${encodeURIComponent(id)}/salespeople/${encodeURIComponent(contactId)}`,
      {
        method: 'PATCH',
        body: JSON.stringify(payload),
      },
      token
    ),

  approveSalesperson: (
    token: string,
    id: string,
    contactId: string,
    approved: boolean
  ) =>
    request<AdminSalesperson>(
      `/sales/projects/${encodeURIComponent(id)}/salespeople/${encodeURIComponent(contactId)}/approval`,
      {
        method: 'PATCH',
        body: JSON.stringify({ approved }),
      },
      token
    ),

  images: (
    token: string,
    id: string
  ) =>
    request<AdminProjectImage[]>(
      `/sales/projects/${encodeURIComponent(id)}/images`,
      {},
      token
    ),

  approveImage: (
    token: string,
    id: string,
    imageId: string,
    approved: boolean
  ) =>
    request<{
      id: string;
      approved: boolean;
    }>(
      `/sales/projects/${encodeURIComponent(id)}/images/${encodeURIComponent(imageId)}/approval`,
      {
        method: 'PATCH',
        body: JSON.stringify({ approved }),
      },
      token
    ),

  replaceImage: async (
    token: string,
    id: string,
    imageId: string,
    file: File
  ): Promise<AdminProjectImage> => {
    const body = new FormData();
    body.append('file', file);

    const response = await fetch(
      `${API_BASE}/api/v1/sales/projects/${encodeURIComponent(id)}/images/${encodeURIComponent(imageId)}`,
      {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body,
      }
    );

    if (!response.ok) {
      const result = await response.json().catch(() => ({}));

      throw new ApiError(
        response.status,
        typeof result.detail === 'string'
          ? result.detail
          : 'Image replacement failed'
      );
    }

    return response.json();
  },

  deleteImage: (
    token: string,
    id: string,
    imageId: string
  ) =>
    request<{
      deleted: boolean;
      id: string;
    }>(
      `/sales/projects/${encodeURIComponent(id)}/images/${encodeURIComponent(imageId)}`,
      {
        method: 'DELETE',
      },
      token
    ),

  imagePreview: async (
    token: string,
    projectId: string,
    imageId: string
  ): Promise<Blob> => {
    const response = await fetch(
      `${API_BASE}/api/v1/sales/projects/${encodeURIComponent(projectId)}/images/${encodeURIComponent(imageId)}/file`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        cache: 'no-store',
      }
    );

    if (!response.ok) {
      throw new ApiError(
        response.status,
        'Could not load preview'
      );
    }

    return response.blob();
  },

  uploadImage: async (
    token: string,
    id: string,
    file: File
  ): Promise<AdminProjectImage> => {
    const body = new FormData();
    body.append('file', file);

    const response = await fetch(
      `${API_BASE}/api/v1/sales/projects/${encodeURIComponent(id)}/images`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body,
      }
    );

    if (!response.ok) {
      const result = await response.json().catch(() => ({}));

      throw new ApiError(
        response.status,
        typeof result.detail === 'string'
          ? result.detail
          : 'Image upload failed'
      );
    }

    return response.json();
  },

  publish: (
    token: string,
    id: string,
    publish: boolean
  ) =>
    request<ManagedProject>(
      `/sales/projects/${encodeURIComponent(id)}/publication`,
      {
        method: 'PATCH',
        body: JSON.stringify({ publish }),
      },
      token
    ),

  facts: (
    token: string,
    projectId: string
  ) =>
    request<FactsAdmin>(
      `/sales/projects/${encodeURIComponent(projectId)}/facts`,
      {},
      token
    ),

  propose: (
    token: string,
    projectId: string,
    key: string,
    value: string
  ) =>
    request<ProjectFact>(
      `/sales/projects/${encodeURIComponent(projectId)}/facts`,
      {
        method: 'POST',
        body: JSON.stringify({ key, value }),
      },
      token
    ),

  review: (
    token: string,
    id: string,
    action: 'approve' | 'reject'
  ) =>
    request<ProjectFact>(
      `/sales/facts/${encodeURIComponent(id)}/review`,
      {
        method: 'POST',
        body: JSON.stringify({ action }),
      },
      token
    ),

  slots: (
    token: string,
    projectId: string
  ) =>
    request<ManagedSlot[]>(
      `/sales/projects/${encodeURIComponent(projectId)}/slots`,
      {},
      token
    ),

  createSlot: (
    token: string,
    project_id: string,
    starts_at: string,
    ends_at: string
  ) =>
    request<{
      slot_id: string;
      project_id: string;
      starts_at: string;
      ends_at: string;
    }>(
      '/sales/slots',
      {
        method: 'POST',
        body: JSON.stringify({
          project_id,
          starts_at,
          ends_at,
        }),
      },
      token
    ),

  setSlotEnabled: (
    token: string,
    id: string,
    enabled: boolean
  ) =>
    request<{
      slot_id: string;
      enabled: boolean;
    }>(
      `/sales/slots/${encodeURIComponent(id)}`,
      {
        method: 'PATCH',
        body: JSON.stringify({ enabled }),
      },
      token
    ),

  reminders: (token: string) =>
    request<ReminderRecord[]>(
      '/sales/reminders',
      {},
      token
    ),
};
