
import { createFileRoute } from '@tanstack/react-router';
import { useEffect, useState } from 'react';
import { PageTitle, Panel } from '@/components/ops';
import { Badge } from '@/components/site';
import { useSalesAuth } from '@/lib/sales-auth';
import {
  salesApi,
  adminApi,
  type FactsAdmin,
  type ManagedSlot,
  type ReminderRecord,
  type ManagedProject,
  type AdminSalesperson,
  type AdminProjectImage,
  type SalespersonForm,
} from '@/lib/sitepilot-api';

export const Route = createFileRoute('/sales/admin')({
  component: Admin,
});

function freshProject() {
  return {
    name: '',
    city: 'Ahmedabad',
    description: '',
    salesperson_name: '',
    salesperson_role: 'Sales executive',
    salesperson_phone: '',
    salesperson_email: '',
  };
}

const emptyContact: SalespersonForm = {
  name: '',
  role_title: 'Sales executive',
  phone: '',
  email: '',
  active: true,
};

const MAX_IMAGE_BYTES = 3 * 1024 * 1024;

function Admin() {
  const { token, user } = useSalesAuth();

  const [project, setProject] = useState('project-1');
  const [projects, setProjects] = useState<ManagedProject[]>([]);
  const [showNew, setShowNew] = useState(false);
  const [newProject, setNewProject] = useState(freshProject);

  const [contacts, setContacts] = useState<AdminSalesperson[]>([]);
  const [photos, setPhotos] = useState<AdminProjectImage[]>([]);
  const [contactDraft, setContactDraft] =
    useState<SalespersonForm>({ ...emptyContact });
  const [editingContact, setEditingContact] = useState<string | null>(null);

  const [imageFile, setImageFile] = useState<File | null>(null);
  const [newProjectFile, setNewProjectFile] = useState<File | null>(null);
  const [photoBusy, setPhotoBusy] = useState(false);

  const [facts, setFacts] = useState<FactsAdmin | null>(null);
  const [slots, setSlots] = useState<ManagedSlot[]>([]);
  const [reminders, setReminders] = useState<ReminderRecord[]>([]);

  const [newSlotAt, setNewSlotAt] = useState('');
  const [key, setKey] = useState('');
  const [value, setValue] = useState('');

  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [revision, setRevision] = useState(0);

  const reload = () => setRevision((v) => v + 1);

  useEffect(() => {
    let mounted = true;

    adminApi
      .projects(token)
      .then((rows) => {
        if (!mounted) return;

        setProjects(rows);

        if (
          rows.length &&
          !rows.some((item) => item.id === project)
        ) {
          setProject(rows[0].id);
        }
      })
      .catch((err) => {
        if (mounted) {
          setError(
            err instanceof Error
              ? err.message
              : 'Cannot list projects'
          );
        }
      });

    return () => {
      mounted = false;
    };
  }, [token, revision]);

  useEffect(() => {
    if (!project) return;

    let mounted = true;

    setLoading(true);
    setError('');

    Promise.all([
      adminApi.facts(token, project),
      adminApi.slots(token, project),
      adminApi.reminders(token),
      adminApi.salespeople(token, project),
      adminApi.images(token, project),
    ])
      .then(([f, s, r, c, i]) => {
        if (!mounted) return;

        setFacts(f);
        setSlots(s);
        setReminders(r);
        setContacts(c);
        setPhotos(i);
      })
      .catch((err) => {
        if (mounted) {
          setError(
            err instanceof Error
              ? err.message
              : 'Unable to load admin data'
          );
        }
      })
      .finally(() => {
        if (mounted) {
          setLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [token, project, revision]);

  async function act(
    task: () => Promise<unknown>,
    message: string
  ) {
    setBusy(true);
    setError('');
    setNotice('');

    try {
      await task();
      setNotice(message);
      reload();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'The action failed'
      );
    } finally {
      setBusy(false);
    }
  }

  async function createProject(
    e: React.FormEvent<HTMLFormElement>
  ) {
    e.preventDefault();

    const contactFields = [
      newProject.salesperson_name.trim(),
      newProject.salesperson_phone.trim(),
      newProject.salesperson_email.trim(),
    ];

    if (
      contactFields.some(Boolean) &&
      !contactFields.every(Boolean)
    ) {
      setError(
        'Provide name, phone and email together when adding a project salesperson.'
      );
      return;
    }

    if (
      newProjectFile &&
      newProjectFile.size > MAX_IMAGE_BYTES
    ) {
      setError('Maximum image size is 3 MB.');
      return;
    }

    setBusy(true);
    setError('');
    setNotice('');

    try {
      const item = await adminApi.addProject(token, {
        name: newProject.name,
        city: newProject.city,
        description: newProject.description,

        ...(newProject.salesperson_name.trim()
          ? {
              salesperson_name: newProject.salesperson_name,
              salesperson_role: newProject.salesperson_role,
              salesperson_phone: newProject.salesperson_phone,
              salesperson_email: newProject.salesperson_email,
            }
          : {}),
      });

      setProjects((current) => [...current, item]);
      setProject(item.id);

      let message =
        'Project draft created. Add approved facts and review photos and contacts before publication.';

      if (newProjectFile) {
        try {
          await adminApi.uploadImage(
            token,
            item.id,
            newProjectFile
          );
        } catch (photoError) {
          message = `Draft created, but image upload failed: ${
            photoError instanceof Error
              ? photoError.message
              : 'Unknown error'
          }`;
        }
      }

      setNewProjectFile(null);
      setNewProject(freshProject());
      setShowNew(false);
      setNotice(message);
      reload();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Could not create project'
      );
    } finally {
      setBusy(false);
    }
  }

  async function uploadProjectPhoto(
    e: React.FormEvent<HTMLFormElement>
  ) {
    e.preventDefault();

    if (!imageFile) return;

    if (imageFile.size > MAX_IMAGE_BYTES) {
      setError('Maximum image size is 3 MB.');
      return;
    }

    setPhotoBusy(true);
    setError('');
    setNotice('');

    try {
      await adminApi.uploadImage(
        token,
        project,
        imageFile
      );

      setImageFile(null);

      const input = document.getElementById(
        'project-photo-upload'
      ) as HTMLInputElement | null;

      if (input) {
        input.value = '';
      }

      setNotice('Image uploaded for approval.');
      reload();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Upload failed'
      );
    } finally {
      setPhotoBusy(false);
    }
  }

  async function replaceProjectPhoto(
    imageId: string,
    file: File
  ) {
    if (file.size > MAX_IMAGE_BYTES) {
      setError('Maximum image size is 3 MB.');
      return;
    }

    if (
      !window.confirm(
        'Replace this image? The current public image will be hidden until the new photo is approved.'
      )
    ) {
      return;
    }

    setPhotoBusy(true);
    setError('');
    setNotice('');

    try {
      await adminApi.replaceImage(
        token,
        project,
        imageId,
        file
      );

      setNotice(
        'Photo replaced. Sales-head approval is required before public display.'
      );

      reload();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Image replacement failed'
      );
    } finally {
      setPhotoBusy(false);
    }
  }

  async function deleteProjectPhoto(imageId: string) {
    if (
      !window.confirm(
        'Permanently delete this photo? This also removes it from the public website and cannot be undone.'
      )
    ) {
      return;
    }

    await act(
      () => adminApi.deleteImage(token, project, imageId),
      'Project photograph deleted.'
    );
  }

  function resetContactDraft() {
    setEditingContact(null);
    setContactDraft({ ...emptyContact });
  }

  const pending =
    facts?.history.filter(
      (item) => item.status === 'pending'
    ) ?? [];

  const fmt = (iso: string) =>
    new Date(iso).toLocaleString('en-IN', {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: 'Asia/Kolkata',
    });

  const selectedProject = projects.find(
    (item) => item.id === project
  );

  return (
    <div className="space-y-6">
      <PageTitle
        id="S5"
        title="Project facts & visits"
      >
        <Badge
          t={pending.length ? 'amber' : 'green'}
          icon={pending.length ? '!' : '✓'}
        >
          {pending.length} awaiting review
        </Badge>
      </PageTitle>

      <p className="text-sm text-muted-foreground">
        Changes here are stored in PostgreSQL. Only
        sales-head-approved facts are shown to buyers.
        Reminders are simulated; no messages are sent.
      </p>

      {user.role === 'sales_head' && (
        <SalesTeamInvitationPanel token={token} />
      )}

      <div className="flex flex-wrap items-end justify-between gap-3">
        <label className="block w-full max-w-sm text-sm font-semibold">
          Project

          <select
            className="mt-1 block w-full rounded-lg border border-input bg-card px-3 py-2"
            value={project}
            onChange={(e) =>
              setProject(e.target.value)
            }
          >
            {projects.map((item) => (
              <option
                key={item.id}
                value={item.id}
              >
                {item.name} (
                {item.published ? 'Published' : 'Draft'})
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          className="btn btn-primary"
          onClick={() =>
            setShowNew((current) => !current)
          }
        >
          {showNew
            ? 'Cancel'
            : 'Add new project'}
        </button>
      </div>

      {showNew && (
        <Panel title="Create a project draft">
          <form
            className="grid gap-3 sm:grid-cols-2"
            onSubmit={createProject}
          >
            <label className="text-sm">
              Project name

              <input
                className="mt-1 w-full rounded-lg border p-3"
                required
                minLength={3}
                maxLength={120}
                value={newProject.name}
                onChange={(e) =>
                  setNewProject((current) => ({
                    ...current,
                    name: e.target.value,
                  }))
                }
              />
            </label>

            <label className="text-sm">
              City

              <input
                className="mt-1 w-full rounded-lg border p-3"
                required
                minLength={2}
                value={newProject.city}
                onChange={(e) =>
                  setNewProject((current) => ({
                    ...current,
                    city: e.target.value,
                  }))
                }
              />
            </label>

            <label className="text-sm sm:col-span-2">
              Draft description

              <textarea
                className="mt-1 w-full rounded-lg border p-3"
                rows={3}
                required
                minLength={10}
                maxLength={1500}
                value={newProject.description}
                onChange={(e) =>
                  setNewProject((current) => ({
                    ...current,
                    description: e.target.value,
                  }))
                }
              />
            </label>

            <div className="rounded-xl border bg-muted/30 p-4 sm:col-span-2">
              <h3 className="font-semibold">
                Project salesperson (optional)
              </h3>

              <p className="mb-3 text-xs text-muted-foreground">
                Enter contact details now or add them later.
                Sales-head approval is required before contact
                information appears to buyers.
              </p>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-sm">
                  Name

                  <input
                    className="mt-1 w-full rounded-lg border p-3"
                    value={newProject.salesperson_name}
                    onChange={(e) =>
                      setNewProject((current) => ({
                        ...current,
                        salesperson_name: e.target.value,
                      }))
                    }
                    placeholder="Full name"
                  />
                </label>

                <label className="text-sm">
                  Job title

                  <input
                    className="mt-1 w-full rounded-lg border p-3"
                    value={newProject.salesperson_role}
                    onChange={(e) =>
                      setNewProject((current) => ({
                        ...current,
                        salesperson_role: e.target.value,
                      }))
                    }
                  />
                </label>

                <label className="text-sm">
                  Phone

                  <input
                    className="mt-1 w-full rounded-lg border p-3"
                    type="tel"
                    pattern="[+]?[0-9]{10,15}"
                    value={newProject.salesperson_phone}
                    onChange={(e) =>
                      setNewProject((current) => ({
                        ...current,
                        salesperson_phone: e.target.value,
                      }))
                    }
                    placeholder="+919876543210"
                  />
                </label>

                <label className="text-sm">
                  Email

                  <input
                    className="mt-1 w-full rounded-lg border p-3"
                    type="email"
                    value={newProject.salesperson_email}
                    onChange={(e) =>
                      setNewProject((current) => ({
                        ...current,
                        salesperson_email: e.target.value,
                      }))
                    }
                    placeholder="sales@example.com"
                  />
                </label>
              </div>
            </div>

            <label className="text-sm sm:col-span-2">
              Project image (optional, pending approval)

              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="mt-1 block w-full rounded-lg border bg-card p-3"
                onChange={(e) =>
                  setNewProjectFile(
                    e.target.files?.[0] ?? null
                  )
                }
              />

              <span className="mt-1 block text-xs text-muted-foreground">
                Maximum 3 MB. You can upload additional
                photos after the draft is created.
              </span>
            </label>

            <button
              type="submit"
              disabled={
                busy ||
                Boolean(
                  newProjectFile &&
                  newProjectFile.size > MAX_IMAGE_BYTES
                )
              }
              className="btn btn-primary sm:col-span-2"
            >
              Save as unpublished draft
            </button>
          </form>
        </Panel>
      )}

      {selectedProject && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border p-3 text-sm">
          <strong>
            Publication:{' '}
            {selectedProject.published
              ? 'Public'
              : 'Draft — hidden from buyers'}
          </strong>

          {facts?.is_sales_head && (
            <button
              type="button"
              className="btn btn-ghost !min-h-9"
              disabled={busy}
              onClick={() =>
                void act(
                  () =>
                    adminApi.publish(
                      token,
                      project,
                      !selectedProject.published
                    ),
                  'Project publication state updated.'
                )
              }
            >
              {selectedProject.published
                ? 'Unpublish'
                : 'Review & publish'}
            </button>
          )}

          <span className="text-muted-foreground">
            Publishing requires an approved RERA
            registration and at least one other approved fact.
          </span>
        </div>
      )}

      {notice && (
        <p
          role="status"
          className="rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm"
        >
          {notice}
        </p>
      )}

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/40 p-3 text-sm"
        >
          {error}

          <button
            type="button"
            className="ml-2 underline"
            onClick={reload}
          >
            Retry
          </button>
        </div>
      )}

      {loading ? (
        <div
          role="status"
          className="rounded-xl border p-8"
        >
          Loading saved project facts and slots…
        </div>
      ) : (
        <div className="grid gap-6 xl:grid-cols-[1.2fr_1fr]">
          <div className="space-y-6">
            {/* PROJECT IMAGE MANAGEMENT */}
            <Panel title="Project images">
              <p className="mb-4 text-sm text-muted-foreground">
                Upload up to eight project photos
                (JPEG, PNG, WebP; maximum 3 MB each).
                Images are stored in PostgreSQL,
                sanitized, and shown publicly only
                after sales-head approval.
              </p>

              <form
                className="flex flex-col gap-3 sm:flex-row sm:items-end"
                onSubmit={uploadProjectPhoto}
              >
                <label className="block flex-1 text-sm">
                  Project photograph

                  <input
                    id="project-photo-upload"
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="mt-2 block w-full rounded-lg border p-3 text-sm"
                    onChange={(e) => {
                      const file =
                        e.target.files?.[0] ?? null;

                      setImageFile(file);

                      setError(
                        file && file.size > MAX_IMAGE_BYTES
                          ? 'Maximum image size is 3 MB.'
                          : ''
                      );
                    }}
                  />
                </label>

                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={
                    !imageFile ||
                    imageFile.size > MAX_IMAGE_BYTES ||
                    photoBusy
                  }
                >
                  {photoBusy
                    ? 'Uploading…'
                    : 'Upload image'}
                </button>
              </form>

              {photos.length ? (
                <ul className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {photos.map((photo) => (
                    <li
                      key={`${photo.id}-${revision}`}
                      className="space-y-2 rounded-xl border p-2"
                    >
                      <AdminPhoto
                        token={token}
                        projectId={project}
                        imageId={photo.id}
                      />

                      <p className="text-xs">
                        {photo.approved
                          ? 'Public (when project is published)'
                          : 'Awaiting review'}
                      </p>

                      {facts?.is_sales_head && (
                        <div className="space-y-2">
                          <button
                            type="button"
                            className="btn btn-ghost !min-h-8 w-full text-xs"
                            disabled={busy || photoBusy}
                            onClick={() =>
                              void act(
                                () =>
                                  adminApi.approveImage(
                                    token,
                                    project,
                                    photo.id,
                                    !photo.approved
                                  ),
                                'Image approval updated.'
                              )
                            }
                          >
                            {photo.approved
                              ? 'Hide from public'
                              : 'Approve photo'}
                          </button>

                          <label className="block text-xs font-semibold">
                            Replace image (requires reapproval)

                            <input
                              type="file"
                              accept="image/jpeg,image/png,image/webp"
                              disabled={busy || photoBusy}
                              className="mt-1 block w-full text-xs"
                              onChange={(e) => {
                                const file =
                                  e.currentTarget.files?.[0];

                                e.currentTarget.value = '';

                                if (file) {
                                  void replaceProjectPhoto(
                                    photo.id,
                                    file
                                  );
                                }
                              }}
                            />
                          </label>

                          <button
                            type="button"
                            className="btn btn-ghost !min-h-8 w-full text-xs text-destructive"
                            disabled={busy || photoBusy}
                            onClick={() =>
                              void deleteProjectPhoto(photo.id)
                            }
                          >
                            Delete photo
                          </button>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-xs text-muted-foreground">
                  No photos uploaded for this project.
                </p>
              )}
            </Panel>

            {/* PROJECT SALESPEOPLE */}
            <Panel title="Project salespeople">
              <p className="mb-4 text-sm text-muted-foreground">
                Add or edit project representatives.
                Buyers see only approved, active contact
                cards when requesting a salesperson
                or viewing the published project.
              </p>

              {contacts.length ? (
                <ul className="mb-5 divide-y rounded-xl border px-3">
                  {contacts.map((contact) => (
                    <li
                      key={contact.id}
                      className="py-3"
                    >
                      <div className="flex flex-wrap justify-between gap-2">
                        <div>
                          <p className="text-sm font-semibold">
                            {contact.name} · {contact.role_title}
                          </p>

                          <p className="text-xs text-muted-foreground">
                            {contact.phone} · {contact.email}
                          </p>

                          <p className="text-xs text-muted-foreground">
                            {!contact.active
                              ? 'Inactive'
                              : contact.approved
                                ? 'Approved for display'
                                : 'Awaiting approval'}
                          </p>
                        </div>

                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            className="btn btn-ghost !min-h-8 text-xs"
                            disabled={busy}
                            onClick={() => {
                              setEditingContact(contact.id);

                              setContactDraft({
                                name: contact.name,
                                role_title: contact.role_title,
                                phone: contact.phone,
                                email: contact.email,
                                active: contact.active,
                              });
                            }}
                          >
                            Edit details
                          </button>

                          {facts?.is_sales_head && (
                            <button
                              type="button"
                              className="btn btn-ghost !min-h-8 text-xs"
                              disabled={busy}
                              onClick={() =>
                                void act(
                                  () =>
                                    adminApi.approveSalesperson(
                                      token,
                                      project,
                                      contact.id,
                                      !contact.approved
                                    ),
                                  'Contact approval updated.'
                                )
                              }
                            >
                              {contact.approved
                                ? 'Revoke display'
                                : 'Approve display'}
                            </button>
                          )}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mb-4 text-sm text-muted-foreground">
                  No salesperson assigned to this project.
                </p>
              )}

              <form
                className="space-y-3 rounded-xl border p-4"
                onSubmit={(e) => {
                  e.preventDefault();

                  const task = editingContact
                    ? () =>
                        adminApi.editSalesperson(
                          token,
                          project,
                          editingContact,
                          contactDraft
                        )
                    : () =>
                        adminApi.addSalesperson(
                          token,
                          project,
                          contactDraft
                        );

                  void act(
                    task,
                    'Salesperson saved. Sales head must approve it for public display.'
                  );

                  resetContactDraft();
                }}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="font-semibold">
                    {editingContact
                      ? 'Edit salesperson'
                      : 'Add salesperson'}
                  </h3>

                  {editingContact && (
                    <button
                      type="button"
                      className="text-sm underline"
                      onClick={resetContactDraft}
                    >
                      Cancel editing
                    </button>
                  )}
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="text-sm">
                    Full name

                    <input
                      className="mt-1 w-full rounded-lg border p-3"
                      required
                      minLength={2}
                      value={contactDraft.name}
                      onChange={(e) =>
                        setContactDraft((current) => ({
                          ...current,
                          name: e.target.value,
                        }))
                      }
                    />
                  </label>

                  <label className="text-sm">
                    Title

                    <input
                      className="mt-1 w-full rounded-lg border p-3"
                      required
                      value={contactDraft.role_title}
                      onChange={(e) =>
                        setContactDraft((current) => ({
                          ...current,
                          role_title: e.target.value,
                        }))
                      }
                    />
                  </label>

                  <label className="text-sm">
                    Phone

                    <input
                      className="mt-1 w-full rounded-lg border p-3"
                      required
                      type="tel"
                      pattern="[+]?[0-9]{10,15}"
                      value={contactDraft.phone}
                      onChange={(e) =>
                        setContactDraft((current) => ({
                          ...current,
                          phone: e.target.value,
                        }))
                      }
                    />
                  </label>

                  <label className="text-sm">
                    Email

                    <input
                      className="mt-1 w-full rounded-lg border p-3"
                      required
                      type="email"
                      value={contactDraft.email}
                      onChange={(e) =>
                        setContactDraft((current) => ({
                          ...current,
                          email: e.target.value,
                        }))
                      }
                    />
                  </label>
                </div>

                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={contactDraft.active}
                    onChange={(e) =>
                      setContactDraft((current) => ({
                        ...current,
                        active: e.target.checked,
                      }))
                    }
                  />

                  Available as a public project contact after approval
                </label>

                <button
                  type="submit"
                  disabled={busy}
                  className="btn btn-primary"
                >
                  {editingContact
                    ? 'Save changes for review'
                    : 'Add salesperson for review'}
                </button>
              </form>
            </Panel>

            {/* APPROVED FACTS */}
            <Panel title="Approved project facts">
              {!facts?.approved.length ? (
                <p className="py-3 text-sm text-muted-foreground">
                  No approved custom facts yet.
                  Project base details remain available.
                </p>
              ) : (
                <ul className="divide-y divide-border">
                  {facts.approved.map((fact) => (
                    <li
                      key={fact.key}
                      className="py-3"
                    >
                      <p className="text-sm font-semibold">
                        {fact.key.replaceAll('_', ' ')}
                      </p>

                      <p className="text-sm">
                        {fact.value}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            {/* FACT PROPOSALS */}
            <Panel title="Propose a fact-sheet change">
              <form
                className="space-y-3"
                onSubmit={(e) => {
                  e.preventDefault();

                  void act(
                    () =>
                      adminApi.propose(
                        token,
                        project,
                        key,
                        value
                      ),
                    'Proposal submitted for sales-head review.'
                  );

                  setKey('');
                  setValue('');
                }}
              >
                <label className="block text-sm">
                  Fact key (letters, numbers, underscores)

                  <input
                    required
                    minLength={3}
                    maxLength={100}
                    pattern="[a-z][a-z0-9_]*"
                    value={key}
                    onChange={(e) =>
                      setKey(e.target.value)
                    }
                    placeholder="parking_policy"
                    className="mt-1 block w-full rounded-lg border border-input bg-card px-3 py-2"
                  />
                </label>

                <label className="block text-sm">
                  Verified statement

                  <textarea
                    required
                    maxLength={700}
                    rows={3}
                    value={value}
                    onChange={(e) =>
                      setValue(e.target.value)
                    }
                    placeholder="Add only client-approved, supportable claims"
                    className="mt-1 block w-full rounded-lg border border-input bg-card p-3"
                  />
                </label>

                <button
                  type="submit"
                  disabled={
                    busy ||
                    !key.trim() ||
                    !value.trim()
                  }
                  className="btn btn-primary"
                >
                  Submit for review
                </button>
              </form>
            </Panel>

            {/* FACT REVIEW QUEUE */}
            <Panel title="Review queue and history">
              {!facts?.history.length ? (
                <p className="text-sm text-muted-foreground">
                  No proposals yet.
                </p>
              ) : (
                <ul className="divide-y divide-border">
                  {facts.history.map((fact) => (
                    <li
                      key={fact.id}
                      className="space-y-2 py-3"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <strong className="text-sm">
                          {fact.key}
                        </strong>

                        <span className="text-xs text-muted-foreground">
                          {fact.status}
                        </span>
                      </div>

                      <p className="break-words text-sm">
                        {fact.value}
                      </p>

                      <p className="text-xs text-muted-foreground">
                        Proposed {fmt(fact.created_at)}
                      </p>

                      {fact.status === 'pending' &&
                        facts.is_sales_head && (
                          <div className="flex gap-2">
                            <button
                              type="button"
                              disabled={busy}
                              className="btn btn-primary !min-h-9 text-xs"
                              onClick={() =>
                                void act(
                                  () =>
                                    adminApi.review(
                                      token,
                                      fact.id,
                                      'approve'
                                    ),
                                  'Fact approved and published.'
                                )
                              }
                            >
                              Approve
                            </button>

                            <button
                              type="button"
                              disabled={busy}
                              className="btn btn-ghost !min-h-9 text-xs"
                              onClick={() =>
                                void act(
                                  () =>
                                    adminApi.review(
                                      token,
                                      fact.id,
                                      'reject'
                                    ),
                                  'Proposal rejected.'
                                )
                              }
                            >
                              Reject
                            </button>
                          </div>
                        )}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>

          <div className="space-y-6">
            {/* VISIT SLOT MANAGEMENT */}
            <Panel title="Upcoming visit slots">
              <form
                className="mb-5 space-y-3 rounded-xl border p-3"
                onSubmit={(e) => {
                  e.preventDefault();

                  if (!newSlotAt) return;

                  const start = new Date(
                    `${newSlotAt}:00+05:30`
                  );

                  const finish = new Date(
                    start.getTime() + 45 * 60 * 1000
                  );

                  void act(
                    () =>
                      adminApi.createSlot(
                        token,
                        project,
                        start.toISOString(),
                        finish.toISOString()
                      ),
                    'A new 45-minute visit slot has been added.'
                  );

                  setNewSlotAt('');
                }}
              >
                <label className="block text-sm font-semibold">
                  Add a 45-minute visit slot (IST)

                  <input
                    required
                    disabled={
                      busy || !selectedProject?.published
                    }
                    type="datetime-local"
                    value={newSlotAt}
                    onChange={(e) =>
                      setNewSlotAt(e.target.value)
                    }
                    className="mt-2 block w-full rounded-lg border p-3"
                  />
                </label>

                <button
                  type="submit"
                  disabled={
                    busy ||
                    !newSlotAt ||
                    !selectedProject?.published
                  }
                  className="btn btn-primary"
                >
                  Add visit time
                </button>

                {!selectedProject?.published && (
                  <p className="text-xs text-muted-foreground">
                    Publish the project before adding bookable slots.
                  </p>
                )}
              </form>

              {!slots.length ? (
                <p className="text-sm text-muted-foreground">
                  No future visit slots.
                </p>
              ) : (
                <ul className="divide-y divide-border">
                  {slots.slice(0, 32).map((slot) => (
                    <li
                      key={slot.slot_id}
                      className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm"
                    >
                      <span>
                        {fmt(slot.starts_at)}
                      </span>

                      <span className="flex items-center gap-2">
                        <span>
                          {slot.enabled
                            ? 'Open'
                            : 'Closed'}
                        </span>

                        <button
                          type="button"
                          disabled={
                            busy ||
                            !facts?.is_sales_head
                          }
                          className="btn btn-ghost !min-h-9 text-xs"
                          onClick={() =>
                            void act(
                              () =>
                                adminApi.setSlotEnabled(
                                  token,
                                  slot.slot_id,
                                  !slot.enabled
                                ),
                              'Slot availability updated.'
                            )
                          }
                        >
                          {slot.enabled
                            ? 'Close'
                            : 'Open'}
                        </button>
                      </span>
                    </li>
                  ))}
                </ul>
              )}

              {!facts?.is_sales_head && (
                <p className="mt-2 text-xs text-muted-foreground">
                  Only the configured sales head can change availability.
                </p>
              )}
            </Panel>

            {/* MOCK REMINDERS */}
            <Panel title="Reminder outbox (mocked)">
              {!reminders.length ? (
                <p className="text-sm text-muted-foreground">
                  No reminders scheduled yet.
                  Confirm a future visit with contact consent
                  to create reminders.
                </p>
              ) : (
                <ul className="divide-y divide-border">
                  {reminders.slice(0, 25).map((reminder) => (
                    <li
                      key={reminder.id}
                      className="py-3 text-sm"
                    >
                      <div className="flex justify-between gap-2">
                        <span>
                          {reminder.kind} before visit
                        </span>

                        <strong>
                          {reminder.status}
                        </strong>
                      </div>

                      <div className="text-xs text-muted-foreground">
                        Due {fmt(reminder.due_at)} ·{' '}
                        {reminder.booking_id.slice(0, 8)}
                      </div>
                    </li>
                  ))}
                </ul>
              )}

              <p className="mt-2 text-xs text-muted-foreground">
                To process due reminders, run{' '}
                <code>
                  python -m app.reminders
                </code>{' '}
                on the backend. No real SMS or WhatsApp is sent.
              </p>
            </Panel>
          </div>
        </div>
      )}
    </div>
  );
}

function AdminPhoto({
  token,
  projectId,
  imageId,
}: {
  token: string;
  projectId: string;
  imageId: string;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;

    setUrl(null);
    setFailed(false);

    adminApi
      .imagePreview(token, projectId, imageId)
      .then((blob) => {
        if (!active) return;

        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (active) {
          setFailed(true);
        }
      });

    return () => {
      active = false;

      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [token, projectId, imageId]);

  if (failed) {
    return (
      <div className="grid aspect-square place-items-center rounded-lg bg-muted p-3 text-center text-xs">
        Image preview unavailable
      </div>
    );
  }

  if (!url) {
    return (
      <div className="grid aspect-square place-items-center rounded-lg bg-muted text-xs">
        Loading image…
      </div>
    );
  }

  return (
    <img
      src={url}
      alt="Uploaded project photograph"
      className="aspect-square w-full rounded-lg object-cover"
    />
  );
}

/** Only rendered for the sales head.
 * Backend independently enforces the role.
 */
function SalesTeamInvitationPanel({
  token,
}: {
  token: string;
}) {
  const [members, setMembers] = useState<
    Array<{
      id: string;
      email: string;
      display_name: string;
      role: string;
    }>
  >([]);

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');

  const [invite, setInvite] = useState<{
    email: string;
    invitation_code: string;
    expires_at: string;
  } | null>(null);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    salesApi
      .team(token)
      .then(setMembers)
      .catch(() =>
        setError('Unable to load sales team')
      );
  }, [token]);

  async function create(
    e: React.FormEvent<HTMLFormElement>
  ) {
    e.preventDefault();

    setBusy(true);
    setError('');
    setInvite(null);

    try {
      const result = await salesApi.createInvitation(
        token,
        email,
        name
      );

      setInvite(result);
      setName('');
      setEmail('');
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Could not create invitation'
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Sales team · invite a new executive">
      <p className="mb-3 text-sm text-muted-foreground">
        Only the sales head can invite a new user.
        The executive uses the one-time code under
        Sales sign in → Activate invitation to choose
        their own password.
      </p>

      <form
        onSubmit={create}
        className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
      >
        <label className="text-sm">
          Executive name

          <input
            className="mt-1 w-full rounded-lg border p-3"
            minLength={2}
            required
            maxLength={120}
            value={name}
            onChange={(e) =>
              setName(e.target.value)
            }
          />
        </label>

        <label className="text-sm">
          Email

          <input
            className="mt-1 w-full rounded-lg border p-3"
            type="email"
            required
            value={email}
            onChange={(e) =>
              setEmail(e.target.value)
            }
          />
        </label>

        <button
          type="submit"
          disabled={busy}
          className="btn btn-primary"
        >
          {busy
            ? 'Creating…'
            : 'Create invitation'}
        </button>
      </form>

      {error && (
        <p
          role="alert"
          className="mt-3 text-sm text-destructive"
        >
          {error}
        </p>
      )}

      {invite && (
        <div
          className="mt-4 rounded-xl border border-primary/30 bg-primary/5 p-4"
          role="status"
        >
          <p className="font-semibold">
            Invitation for {invite.email}
          </p>

          <p className="mt-1 text-sm">
            Expires:{' '}
            {new Date(
              invite.expires_at
            ).toLocaleString('en-IN')}.
            Share privately; this code is shown only once.
          </p>

          <code className="mt-2 block break-all rounded-lg bg-card p-3 text-xs">
            {invite.invitation_code}
          </code>

          <button
            type="button"
            className="btn btn-ghost mt-2"
            onClick={() =>
              void navigator.clipboard.writeText(
                invite.invitation_code
              )
            }
          >
            Copy invitation code
          </button>
        </div>
      )}

      <p className="mt-5 text-sm font-semibold">
        Existing team ({members.length})
      </p>

      <div className="mt-2 divide-y rounded-xl border">
        {members.map((member) => (
          <div
            key={member.id}
            className="flex flex-wrap justify-between gap-2 p-3 text-sm"
          >
            <span>
              {member.display_name} · {member.email}
            </span>

            <span className="text-muted-foreground">
              {member.role === 'sales_head'
                ? 'Sales head'
                : 'Sales executive'}
            </span>
          </div>
        ))}
      </div>
    </Panel>
  );
}
