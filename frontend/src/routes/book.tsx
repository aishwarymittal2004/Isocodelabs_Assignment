
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { useEffect, useState, type FormEvent } from 'react';
import { SiteHeader, DemoNote } from '@/components/site';
import { projects, getProject } from '@/lib/mock-data';
import {
  sitepilotApi,
  backendProjectId,
  buyerSession,
  ApiError,
  type ApiSlot,
  type ApiProject,
} from '@/lib/sitepilot-api';

type Search = {
  project?: string;
};

export const Route = createFileRoute('/book')({
  validateSearch: (s: Record<string, unknown>): Search => ({
    project: typeof s.project === 'string' ? s.project : undefined,
  }),
  component: Book,
});

function localDate(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');

  return `${year}-${month}-${day}`;
}

function makeDays() {
  return Array.from({ length: 14 }, (_, i) => {
    const d = new Date();
    d.setHours(12, 0, 0, 0);
    d.setDate(d.getDate() + i + 1);

    return {
      key: localDate(d),
      label: d.toLocaleDateString('en-IN', {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
      }),
    };
  });
}

function showTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-IN', {
    timeZone: 'Asia/Kolkata',
    hour: 'numeric',
    minute: '2-digit',
  });
}

type AvailabilityStatus =
  | 'loading'
  | 'available'
  | 'full'
  | 'error';

type AvailabilityMap = Record<string, AvailabilityStatus>;

function monthStart(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function monthIdentifier(date: Date): number {
  return date.getFullYear() * 12 + date.getMonth();
}

function BookingCalendar({
  days,
  projectId,
  selectedDate,
  onSelectDate,
  availability,
}: {
  days: ReturnType<typeof makeDays>;
  projectId: string;
  selectedDate: string;
  onSelectDate: (date: string) => void;
  availability: AvailabilityMap;
}) {
  const [currentMonth, setCurrentMonth] = useState(() =>
    monthStart(new Date(days[0].key + 'T12:00:00'))
  );

  const firstAllowed = days[0].key;
  const lastAllowed = days[days.length - 1].key;

  const firstAllowedMonth = monthIdentifier(
    new Date(firstAllowed + 'T12:00:00')
  );

  const lastAllowedMonth = monthIdentifier(
    new Date(lastAllowed + 'T12:00:00')
  );

  const currentMonthId = monthIdentifier(currentMonth);

  const canGoPrevious = currentMonthId > firstAllowedMonth;
  const canGoNext = currentMonthId < lastAllowedMonth;

  useEffect(() => {
    setCurrentMonth(
      monthStart(new Date(days[0].key + 'T12:00:00'))
    );
  }, [days, projectId]);

  const year = currentMonth.getFullYear();
  const month = currentMonth.getMonth();

  const totalDays = new Date(year, month + 1, 0).getDate();

  // Monday-first calendar.
  const firstDayOffset =
    (new Date(year, month, 1).getDay() + 6) % 7;

  const calendarCells = [
    ...Array.from({ length: firstDayOffset }, () => null),
    ...Array.from({ length: totalDays }, (_, i) => i + 1),
  ];

  const monthLabel = currentMonth.toLocaleDateString('en-IN', {
    month: 'long',
    year: 'numeric',
  });

  return (
    <div className="mt-5 w-full max-w-xl rounded-[1.75rem] border border-border bg-card p-4 shadow-sm sm:p-6">
      <div className="mb-6 flex items-center justify-between gap-3">
        <button
          type="button"
          aria-label="Previous month"
          disabled={!canGoPrevious}
          onClick={() =>
            setCurrentMonth(
              new Date(year, month - 1, 1)
            )
          }
          className="flex h-10 w-10 items-center justify-center rounded-full border border-border text-lg transition hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-30"
        >
          ‹
        </button>

        <h3 className="text-center font-display text-xl font-semibold">
          {monthLabel}
        </h3>

        <button
          type="button"
          aria-label="Next month"
          disabled={!canGoNext}
          onClick={() =>
            setCurrentMonth(
              new Date(year, month + 1, 1)
            )
          }
          className="flex h-10 w-10 items-center justify-center rounded-full border border-border text-lg transition hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-30"
        >
          ›
        </button>
      </div>

      <div className="grid grid-cols-7 gap-1 text-center sm:gap-2">
        {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(
          (name) => (
            <div
              key={name}
              className="pb-3 text-xs font-semibold text-muted-foreground"
            >
              {name}
            </div>
          )
        )}

        {calendarCells.map((day, index) => {
          if (day === null) {
            return (
              <div
                key={`empty-${index}`}
                aria-hidden="true"
                className="h-11"
              />
            );
          }

          const dateObject = new Date(year, month, day);
          const dateKey = localDate(dateObject);

          const inBookingWindow =
            dateKey >= firstAllowed &&
            dateKey <= lastAllowed;

          const status = availability[dateKey];

          const isAvailable =
            inBookingWindow &&
            status === 'available';

          const isSelected = selectedDate === dateKey;

          const isLoading =
            inBookingWindow &&
            (!status || status === 'loading');

          const isFullyBooked =
            inBookingWindow &&
            status === 'full';

          const hasError =
            inBookingWindow &&
            status === 'error';

          const disabled = !isAvailable;

          let dateDescription = 'Outside booking window';

          if (isFullyBooked) {
            dateDescription = 'Fully booked';
          } else if (isLoading) {
            dateDescription = 'Checking availability';
          } else if (hasError) {
            dateDescription = 'Availability unavailable';
          } else if (isAvailable) {
            dateDescription = 'Available';
          }

          return (
            <button
              key={dateKey}
              type="button"
              disabled={disabled}
              aria-pressed={isSelected}
              aria-label={`${dateObject.toLocaleDateString('en-IN', {
                day: 'numeric',
                month: 'long',
                year: 'numeric',
              })}, ${dateDescription}`}
              title={dateDescription}
              onClick={() => onSelectDate(dateKey)}
              className={[
                'relative flex h-11 w-full items-center justify-center rounded-xl border text-sm font-medium transition-all',
                isSelected
                  ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                  : isAvailable
                    ? 'border-border bg-background text-foreground hover:border-primary hover:bg-secondary'
                    : 'cursor-not-allowed border-transparent bg-secondary/50 text-muted-foreground/50',
              ].join(' ')}
            >
              {day}

              {isLoading && (
                <span
                  aria-hidden="true"
                  className="absolute bottom-1 h-1 w-1 rounded-full bg-muted-foreground/50"
                />
              )}
            </button>
          );
        })}
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-3 border-t border-border pt-5 text-xs text-muted-foreground">
        <span className="flex items-center gap-2">
          <span className="h-3 w-3 rounded border border-primary bg-background" />
          Available
        </span>

        <span className="flex items-center gap-2">
          <span className="h-3 w-3 rounded bg-secondary" />
          Fully booked / unavailable
        </span>

        <span className="flex items-center gap-2">
          <span className="h-3 w-3 rounded bg-primary" />
          Selected
        </span>
      </div>

      <p className="mt-4 text-xs text-muted-foreground">
        Dates are enabled only when the booking server reports
        at least one available visit slot.
        Bookings are currently offered for the next 14 days.
      </p>
    </div>
  );
}

function Book() {
  const search = Route.useSearch();
  const navigate = useNavigate();

  const [days] = useState(makeDays);

  const [step, setStep] = useState(search.project ? 2 : 1);
  const [project, setProject] = useState(search.project ?? '');

  const [liveProjects, setLiveProjects] = useState<ApiProject[]>([]);

  const [accountMode, setAccountMode] =
    useState<'register' | 'login'>('register');

  const [password, setPassword] = useState('');

  const [date, setDate] = useState('');
  const [slots, setSlots] = useState<ApiSlot[]>([]);
  const [selected, setSelected] = useState('');

  const [loadingSlots, setLoadingSlots] = useState(false);
  const [busy, setBusy] = useState(false);

  const [availability, setAvailability] =
    useState<AvailabilityMap>({});

  const [error, setError] = useState('');

  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [consent, setConsent] = useState(false);

  const p = getProject(project);

  const liveProject = liveProjects.find(
    (x) => x.id === backendProjectId(project)
  );

  const displayName =
    p?.name ?? liveProject?.name ?? 'Project';

  const selectedSlot = slots.find(
    (slot) => slot.slot_id === selected
  );

  // Load published projects from the FastAPI backend.
  useEffect(() => {
    sitepilotApi
      .projects()
      .then(setLiveProjects)
      .catch(() =>
        setError('Unable to retrieve the published projects.')
      );
  }, []);

  // Check actual availability for every date in the
  // existing 14-day booking window.
  //
  // Run requests in batches of four to avoid sending
  // all 14 requests simultaneously.
  useEffect(() => {
    if (!project) {
      setAvailability({});
      return;
    }

    let active = true;

    const backendId = backendProjectId(project);

    const initial: AvailabilityMap = {};

    for (const day of days) {
      initial[day.key] = 'loading';
    }

    setAvailability(initial);

    async function checkCalendarAvailability() {
      for (let i = 0; i < days.length; i += 4) {
        if (!active) return;

        const batch = days.slice(i, i + 4);

        await Promise.all(
          batch.map(async (day) => {
            try {
              const result = await sitepilotApi.slots(
                backendId,
                day.key
              );

              if (!active) return;

              const hasAvailableSlot = result.slots.some(
                (slot) => slot.available
              );

              setAvailability((previous) => ({
                ...previous,
                [day.key]: hasAvailableSlot
                  ? 'available'
                  : 'full',
              }));
            } catch {
              if (!active) return;

              // Do not mark API failures as fully booked.
              // Keep the date disabled until availability
              // can be verified.
              setAvailability((previous) => ({
                ...previous,
                [day.key]: 'error',
              }));
            }
          })
        );
      }
    }

    void checkCalendarAvailability();

    return () => {
      active = false;
    };
  }, [project, days]);

  // Load the available time slots for the selected date.
  useEffect(() => {
    if (!project || !date) {
      setSlots([]);
      setSelected('');
      return;
    }

    let active = true;

    setLoadingSlots(true);
    setError('');
    setSelected('');
    setSlots([]);

    const backendId = backendProjectId(project);

    sitepilotApi
      .slots(backendId, date)
      .then((result) => {
        if (!active) return;

        setSlots(result.slots);

        const hasAvailableSlot = result.slots.some(
          (slot) => slot.available
        );

        setAvailability((previous) => ({
          ...previous,
          [date]: hasAvailableSlot
            ? 'available'
            : 'full',
        }));

        if (!hasAvailableSlot) {
          setDate('');
        }
      })
      .catch((err) => {
        if (!active) return;

        setAvailability((previous) => ({
          ...previous,
          [date]: 'error',
        }));

        setError(
          err instanceof Error
            ? err.message
            : 'Could not load slots'
        );
      })
      .finally(() => {
        if (active) {
          setLoadingSlots(false);
        }
      });

    return () => {
      active = false;
    };
  }, [project, date]);

  function selectDate(nextDate: string) {
    if (availability[nextDate] !== 'available') {
      return;
    }

    setSelected('');
    setDate(nextDate);
    setError('');
  }

  function chooseProject(nextProject: string) {
    setProject(nextProject);
    setDate('');
    setSlots([]);
    setSelected('');
    setAvailability({});
    setError('');
    setStep(2);
  }

  async function confirm(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();

    if (!selectedSlot || busy) return;

    if (
      !/^\d{10}$/.test(phone.replace(/\s/g, '')) ||
      (accountMode === 'register' && name.trim().length < 2)
    ) {
      setError(
        accountMode === 'register'
          ? 'Enter your name and a 10-digit mobile number.'
          : 'Enter your 10-digit mobile number.'
      );
      return;
    }

    setBusy(true);
    setError('');

    const backendId = backendProjectId(project);

    try {
      const lead =
        accountMode === 'register'
          ? await sitepilotApi.registerBuyer({
              name: name.trim(),
              phone: phone.replace(/\s/g, ''),
              password,
              project_id: backendId,
              contact_consent: consent,
            })
          : await sitepilotApi.loginBuyer(
              phone.replace(/\s/g, ''),
              password,
              backendId
            );

      buyerSession.save(
        backendId,
        lead.buyer_session_token
      );

      setAccountMode('login');

      const booking = await sitepilotApi.book(
        backendId,
        selectedSlot.slot_id,
        lead.buyer_session_token,
        crypto.randomUUID()
      );

      if (booking.status !== 'confirmed') {
        throw new Error(
          'Booking is not confirmed. Please review your visits.'
        );
      }

      buyerSession.save(
        booking.booking_id,
        lead.buyer_session_token
      );

      buyerSession.save(
        backendId,
        lead.buyer_session_token
      );

      navigate({
        to: '/booking/confirmed',
        search: {
          project,
          date:
            days.find((d) => d.key === date)?.label ??
            date,
          time: showTime(booking.starts_at),
          ref: booking.booking_id,
        },
      });
    } catch (err) {
      if (
        err instanceof ApiError &&
        err.status === 409 &&
        /account exists/i.test(err.detail)
      ) {
        setAccountMode('login');
        setPassword('');

        setError(
          'An account already exists for this phone and project. Sign in using its original password to continue your booking. If you forgot it, request an identity-verified reset.'
        );
      } else if (
        err instanceof ApiError &&
        (err.status === 409 || err.status === 404)
      ) {
        setError(
          'That time is no longer available. Please select another slot.'
        );

        setSelected('');
        setStep(2);

        try {
          const latest = await sitepilotApi.slots(
            backendId,
            date
          );

          setSlots(latest.slots);

          const stillAvailable = latest.slots.some(
            (slot) => slot.available
          );

          setAvailability((previous) => ({
            ...previous,
            [date]: stillAvailable
              ? 'available'
              : 'full',
          }));

          if (!stillAvailable) {
            setDate('');
          }
        } catch {
          setAvailability((previous) => ({
            ...previous,
            [date]: 'error',
          }));
        }
      } else {
        setError(
          err instanceof Error
            ? err.message
            : 'Could not confirm booking'
        );
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen">
      <SiteHeader />

      <main className="mx-auto max-w-5xl px-5 py-12 md:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="eyebrow">Site visit</p>

            <h1 className="mt-2 text-4xl md:text-6xl">
              Plan your visit
            </h1>
          </div>

          <DemoNote>
            Live booking via FastAPI · Sample project data
          </DemoNote>
        </div>

        <ol
          className="mt-10 grid grid-cols-3 gap-2"
          aria-label="Booking progress"
        >
          {['Project', 'Date & time', 'Confirm'].map(
            (label, index) => (
              <li
                key={label}
                aria-current={
                  step === index + 1
                    ? 'step'
                    : undefined
                }
                className={`border-t-2 pt-3 text-sm ${
                  step >= index + 1
                    ? 'border-primary font-semibold'
                    : 'border-border text-muted-foreground'
                }`}
              >
                0{index + 1} · {label}
              </li>
            )
          )}
        </ol>

        {error && (
          <div
            role="alert"
            className="mt-6 rounded-2xl border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive"
          >
            {error}
          </div>
        )}

        {/* STEP 1 — PROJECT SELECTION */}
        {step === 1 && (
          <div className="mt-10 grid gap-6 md:grid-cols-2">
            {liveProjects.map((item) => {
              const original = projects.find(
                (q) => backendProjectId(q.id) === item.id
              );

              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => chooseProject(item.id)}
                  className="group overflow-hidden rounded-[1.75rem] border-2 border-transparent text-left hover:border-primary"
                >
                  {original ? (
                    <img
                      src={original.image}
                      alt="Illustrative project imagery"
                      className="aspect-[16/9] w-full object-cover"
                    />
                  ) : (
                    <div className="grid aspect-[16/9] place-items-center bg-secondary text-sm">
                      Project imagery not yet approved
                    </div>
                  )}

                  <div className="bg-card p-5">
                    <h2 className="font-display text-2xl">
                      {item.name}
                    </h2>

                    <p className="text-sm text-muted-foreground">
                      {item.city} · {item.description}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        )}

        {/* STEP 2 — CALENDAR AND TIME SLOTS */}
        {step === 2 && (p || liveProject) && (
          <div className="mt-10 grid gap-10 lg:grid-cols-[1fr_320px]">
            <section className="min-w-0">
              <h2 className="text-2xl">
                Choose a date
              </h2>

              <BookingCalendar
                days={days}
                projectId={project}
                selectedDate={date}
                availability={availability}
                onSelectDate={selectDate}
              />

              <h2 className="mt-10 text-2xl">
                Available times
              </h2>

              {!date ? (
                <p className="mt-4 rounded-2xl border border-dashed p-6">
                  Choose an available date from the calendar
                  to see real visit slots.
                </p>
              ) : loadingSlots ? (
                <p
                  role="status"
                  className="mt-4"
                >
                  Checking availability…
                </p>
              ) : slots.length === 0 ? (
                <p className="mt-4 rounded-2xl border border-dashed p-6">
                  No slots on this day. Please choose another date.
                </p>
              ) : (
                <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {slots.map((slot) => (
                    <button
                      key={slot.slot_id}
                      type="button"
                      disabled={!slot.available}
                      aria-pressed={
                        selected === slot.slot_id
                      }
                      onClick={() =>
                        setSelected(slot.slot_id)
                      }
                      className={`min-h-14 rounded-2xl border p-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-40 ${
                        selected === slot.slot_id
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'border-border bg-card'
                      }`}
                    >
                      {showTime(slot.starts_at)}

                      {!slot.available && (
                        <span className="block text-xs">
                          Unavailable
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}

              <div className="mt-8 flex gap-3">
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => setStep(1)}
                >
                  Change project
                </button>

                <button
                  type="button"
                  disabled={!selected}
                  onClick={() => {
                    setError('');
                    setStep(3);
                  }}
                  className="btn btn-primary"
                >
                  Continue
                </button>
              </div>
            </section>

            <Summary
              name={displayName}
              date={date}
              slot={selectedSlot}
            />
          </div>
        )}

        {/* STEP 3 — BUYER ACCOUNT AND CONFIRMATION */}
        {step === 3 &&
          (p || liveProject) &&
          selectedSlot && (
            <div className="mt-10 grid gap-10 lg:grid-cols-[1fr_320px]">
              <form
                onSubmit={confirm}
                className="space-y-5"
              >
                <h2 className="text-2xl">
                  Buyer account
                </h2>

                <p className="text-sm text-muted-foreground">
                  Create a password-protected account so you
                  can return to cancel a booking. Already
                  registered for this project? Sign in instead.
                </p>

                <div className="flex gap-2">
                  <button
                    type="button"
                    className={
                      accountMode === 'register'
                        ? 'btn btn-primary'
                        : 'btn btn-ghost'
                    }
                    onClick={() =>
                      setAccountMode('register')
                    }
                  >
                    Create account
                  </button>

                  <button
                    type="button"
                    className={
                      accountMode === 'login'
                        ? 'btn btn-primary'
                        : 'btn btn-ghost'
                    }
                    onClick={() =>
                      setAccountMode('login')
                    }
                  >
                    Sign in
                  </button>
                </div>

                {accountMode === 'register' && (
                  <label className="block text-sm font-semibold">
                    Name

                    <input
                      required
                      minLength={2}
                      value={name}
                      onChange={(e) =>
                        setName(e.target.value)
                      }
                      className="mt-2 h-12 w-full rounded-xl border border-input bg-card px-4"
                    />
                  </label>
                )}

                <label className="block text-sm font-semibold">
                  Mobile number

                  <input
                    required
                    inputMode="numeric"
                    pattern="[0-9]{10}"
                    value={phone}
                    onChange={(e) =>
                      setPhone(e.target.value)
                    }
                    className="mt-2 h-12 w-full rounded-xl border border-input bg-card px-4"
                  />
                </label>

                <label className="block text-sm font-semibold">
                  Password

                  <input
                    required
                    type="password"
                    minLength={10}
                    maxLength={128}
                    autoComplete={
                      accountMode === 'login'
                        ? 'current-password'
                        : 'new-password'
                    }
                    value={password}
                    onChange={(e) =>
                      setPassword(e.target.value)
                    }
                    className="mt-2 h-12 w-full rounded-xl border border-input bg-card px-4"
                  />
                </label>

                {accountMode === 'register' && (
                  <label className="flex gap-3 text-sm">
                    <input
                      type="checkbox"
                      checked={consent}
                      onChange={(e) =>
                        setConsent(e.target.checked)
                      }
                    />

                    <span>
                      Optional: I agree to reminders and
                      follow-up contact. You can book
                      without selecting this checkbox.
                    </span>
                  </label>
                )}

                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => setStep(2)}
                    className="btn btn-ghost"
                  >
                    Back
                  </button>

                  <button
                    type="submit"
                    disabled={busy}
                    className="btn btn-primary"
                  >
                    {busy
                      ? 'Confirming with server…'
                      : 'Confirm booking'}
                  </button>
                </div>

                <p className="text-xs text-muted-foreground">
                  A visit is confirmed only after the server
                  records it. No message is sent automatically.
                </p>
              </form>

              <Summary
                name={displayName}
                date={date}
                slot={selectedSlot}
              />
            </div>
          )}

        {step > 1 && !p && !liveProject && (
          <p className="mt-10">
            Invalid project.{' '}
            <Link
              to="/book"
              className="underline"
            >
              Start again
            </Link>
          </p>
        )}
      </main>
    </div>
  );
}

function Summary({
  name,
  date,
  slot,
}: {
  name: string;
  date: string;
  slot: ApiSlot | undefined;
}) {
  return (
    <aside className="card-surface h-fit p-6 shadow-soft">
      <p className="eyebrow">
        Summary
      </p>

      <p className="mt-3 font-display text-2xl">
        {name}
      </p>

      <dl className="mt-4 space-y-3 text-sm">
        <div className="flex justify-between border-t border-border pt-3">
          <dt>Date</dt>
          <dd>{date || '—'}</dd>
        </div>

        <div className="flex justify-between border-t border-border pt-3">
          <dt>Time</dt>
          <dd>
            {slot
              ? showTime(slot.starts_at)
              : '—'}
          </dd>
        </div>
      </dl>

      <p className="mt-4 rounded-xl bg-secondary px-3 py-2 text-xs">
        Selected is not confirmed until you submit.
      </p>
    </aside>
  );
}
