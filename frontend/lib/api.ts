import {
  getDemoOffre,
  getDemoOffres,
  updateDemoOffre,
  useDemoMode,
} from "./demo-offers";
import type { Offre, OffreUpdatePayload, StatutOffre } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

function offreToDocxPayload(offre: Offre) {
  return {
    numero_offre: offre.numero_offre,
    expediteur_nom: offre.expediteur_nom,
    expediteur_email: offre.expediteur_email,
    sujet: offre.sujet,
    created_at: offre.created_at,
    texte_intro: offre.texte_intro,
    texte_conclusion: offre.texte_conclusion,
    montant_ht: offre.montant_ht,
    montant_tva: offre.montant_tva,
    montant_ttc: offre.montant_ttc,
    lignes: offre.lignes,
  };
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store", ...init });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function fetchOffres(statut?: StatutOffre | "tous"): Promise<Offre[]> {
  const query = statut && statut !== "tous" ? `?statut=${statut}` : "";

  if (useDemoMode()) {
    try {
      const data = await apiFetch<Offre[]>(`/quotes${query}`);
      if (data.length > 0) return data;
    } catch {
      /* backend indisponible → démo */
    }
    return getDemoOffres(statut);
  }

  return apiFetch<Offre[]>(`/quotes${query}`);
}

export async function fetchOffre(id: string): Promise<Offre> {
  if (useDemoMode() && id.startsWith("demo-")) {
    const demo = getDemoOffre(id);
    if (demo) return demo;
  }

  if (useDemoMode()) {
    try {
      return await apiFetch<Offre>(`/quotes/${id}`);
    } catch {
      const demo = getDemoOffre(id);
      if (!demo) throw new Error("Offre introuvable");
      return demo;
    }
  }
  return apiFetch<Offre>(`/quotes/${id}`);
}

export async function saveOffre(id: string, payload: OffreUpdatePayload): Promise<void> {
  if (useDemoMode()) {
    try {
      await apiFetch(`/quotes/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return;
    } catch {
      updateDemoOffre(id, payload);
      return;
    }
  }

  await apiFetch(`/quotes/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function downloadOffreDocument(offre: Offre): Promise<void> {
  const filename = `${offre.numero_offre.replace(/\//g, "-")}.docx`;

  if (!offre.id.startsWith("demo-")) {
    try {
      const res = await fetch(`${API_BASE}/quotes/${offre.id}/document`, {
        cache: "no-store",
      });
      if (res.ok) {
        triggerBlobDownload(await res.blob(), filename);
        return;
      }
    } catch {
      /* fallback generate-document */
    }
  }

  const res = await fetch(`${API_BASE}/quotes/generate-document`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(offreToDocxPayload(offre)),
  });
  if (!res.ok) throw new Error("Échec de la génération DOCX");
  triggerBlobDownload(await res.blob(), filename);
}

export async function validateAndSendOffre(id: string, offre?: Offre): Promise<void> {
  if (useDemoMode() || id.startsWith("demo-")) {
    if (offre) {
      await downloadOffreDocument(offre);
    }
    try {
      await apiFetch(`/quotes/${id}/validate-and-send`, { method: "POST" });
      return;
    } catch {
      if (offre) updateDemoOffre(id, { statut: "envoyee" });
      return;
    }
  }
  await apiFetch(`/quotes/${id}/validate-and-send?validated_by=employe@boss.fr`, {
    method: "POST",
  });
  if (offre) await downloadOffreDocument(offre);
}

export async function rejectOffre(id: string): Promise<void> {
  if (useDemoMode()) {
    try {
      await apiFetch(`/quotes/${id}/refuser`, { method: "POST" });
      return;
    } catch {
      updateDemoOffre(id, { statut: "refusee" });
      return;
    }
  }
  await apiFetch(`/quotes/${id}/refuser`, { method: "POST" });
}

export async function processEmailIntoQuote(emailId: string): Promise<{ quote_id: string; numero_offre: string }> {
  const res = await fetch(`${API_BASE}/emails/${emailId}/process`, {
    method: "POST",
    cache: "no-store",
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Erreur API ${res.status}`);
  }
  return res.json();
}
