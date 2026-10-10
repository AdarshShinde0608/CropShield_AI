import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { createFieldAction, listFieldActions, updateAction } from "../../api/actions";
import type { ActionOut, ActionStatus } from "../../types/api";

const statuses: ActionStatus[] = ["pending", "done", "needs_expert"];

export default function ActionTracker({ fieldId }: { fieldId: string }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<ActionStatus>("pending");
  const [note, setNote] = useState("");
  const actionsQuery = useQuery({
    queryKey: ["field-actions", fieldId],
    queryFn: () => listFieldActions(fieldId)
  });
  const createMutation = useMutation({
    mutationFn: () => createFieldAction(fieldId, { status, note: note.trim() || null }),
    onSuccess: async () => {
      setNote("");
      await queryClient.invalidateQueries({ queryKey: ["field-actions", fieldId] });
    }
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, update }: { id: string; update: { status?: ActionStatus; note?: string } }) =>
      updateAction(id, update),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["field-actions", fieldId] })
  });

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-5 sm:p-7" aria-labelledby="action-tracker-title">
      <h2 id="action-tracker-title" className="text-lg font-semibold text-slate-950">{t("actions.title")}</h2>
      <form
        className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          createMutation.mutate();
        }}
      >
        <label className="text-xs font-semibold text-slate-600">
          {t("actions.status")}
          <select className="form-select mt-1 w-full rounded-lg border-stone-300 text-sm" onChange={(event) => setStatus(event.target.value as ActionStatus)} value={status}>
            {statuses.map((item) => <option key={item} value={item}>{t(`actions.${item}`)}</option>)}
          </select>
        </label>
        <label className="text-xs font-semibold text-slate-600">
          {t("actions.note")}
          <textarea className="form-textarea mt-1 w-full resize-y rounded-lg border-stone-300 text-sm" maxLength={500} onChange={(event) => setNote(event.target.value)} rows={2} value={note} />
        </label>
        <button className="self-end rounded-lg bg-brand-700 px-4 py-2.5 text-sm font-bold text-white hover:bg-brand-800 disabled:opacity-60" disabled={createMutation.isPending} type="submit">
          {createMutation.isPending ? t("common.loading") : t("actions.add")}
        </button>
      </form>
      {(createMutation.isError || updateMutation.isError) && (
        <p className="mt-3 text-sm text-red-700" role="alert">{t("actions.saveError")}</p>
      )}
      {actionsQuery.isLoading && <p className="mt-4 text-sm text-slate-600" role="status">{t("common.loading")}</p>}
      {actionsQuery.isError && <p className="mt-4 text-sm text-red-700" role="alert">{t("actions.loadError")}</p>}
      {actionsQuery.data && actionsQuery.data.length === 0 && <p className="mt-4 text-sm text-slate-500">{t("actions.empty")}</p>}
      {actionsQuery.data && actionsQuery.data.length > 0 && (
        <ul className="mt-5 divide-y divide-stone-100">
          {actionsQuery.data.map((action) => (
            <ActionRow
              action={action}
              busy={updateMutation.isPending}
              key={action.id}
              onUpdate={(nextStatus) => updateMutation.mutate({ id: action.id, update: { status: nextStatus } })}
              onNoteUpdate={(nextNote) => updateMutation.mutate({ id: action.id, update: { note: nextNote } })}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function ActionRow({
  action,
  busy,
  onUpdate,
  onNoteUpdate
}: {
  action: ActionOut;
  busy: boolean;
  onUpdate: (status: ActionStatus) => void;
  onNoteUpdate: (note: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const [note, setNote] = useState(action.note ?? "");
  return (
    <li className="space-y-3 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-900">{t(`actions.${action.status}`)}</p>
          {action.note && <p className="mt-1 break-words text-sm text-slate-600">{action.note}</p>}
          <time className="mt-1 block text-xs text-slate-500" dateTime={action.updated_at}>{new Date(action.updated_at).toLocaleDateString(i18n.resolvedLanguage)}</time>
        </div>
        <label className="text-xs font-semibold text-slate-600">
          {t("actions.updateStatus")}
          <select
            aria-label={t("actions.updateStatus")}
            className="form-select ml-2 rounded-lg border-stone-300 text-sm"
            disabled={busy}
            onChange={(event) => {
              const nextStatus = statuses.find((item) => item === event.target.value);
              if (nextStatus) onUpdate(nextStatus);
            }}
            value={action.status}
          >
            {statuses.map((item) => <option key={item} value={item}>{t(`actions.${item}`)}</option>)}
          </select>
        </label>
      </div>
      <form className="flex flex-wrap gap-2" onSubmit={(event) => { event.preventDefault(); onNoteUpdate(note); }}>
        <label className="sr-only" htmlFor={`action-note-${action.id}`}>{t("actions.note")}</label>
        <input
          className="form-input min-w-0 flex-1 rounded-lg border-stone-300 text-sm"
          id={`action-note-${action.id}`}
          maxLength={500}
          onChange={(event) => setNote(event.target.value)}
          value={note}
        />
        <button className="rounded-lg border border-stone-300 px-3 py-2 text-xs font-bold text-slate-700 hover:bg-stone-50 disabled:opacity-50" disabled={busy || note === (action.note ?? "")} type="submit">
          {t("actions.saveNote")}
        </button>
      </form>
    </li>
  );
}
