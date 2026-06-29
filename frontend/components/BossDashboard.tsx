"use client";

import { useCallback, useEffect, useState } from "react";
import {
  downloadOffreDocument,
  fetchOffre,
  fetchOffres,
  processEmailIntoQuote,
  rejectOffre,
  saveOffre,
  validateAndSendOffre,
} from "@/lib/api";
import {
  STATUT_CONFIG,
  formatDate,
  formatEur,
  type LigneOffre,
  type Offre,
  type StatutOffre,
} from "@/lib/types";
import { webhookClient } from "@/lib/webhook-client";

export default function BossDashboard() {
  const [offres, setOffres] = useState<Offre[]>([]);
  const [allOffres, setAllOffres] = useState<Offre[]>([]);
  const [offreSelectionnee, setOffreSelectionnee] = useState<Offre | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [filtre, setFiltre] = useState<StatutOffre | "tous">("tous");
  const [notification, setNotification] = useState<{
    msg: string;
    type: "ok" | "err";
  } | null>(null);

  const notifier = useCallback((msg: string, type: "ok" | "err") => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 3500);
  }, []);

  const chargerOffres = useCallback(async () => {
    setLoading(true);
    try {
      const [filtered, all] = await Promise.all([
        fetchOffres(filtre),
        fetchOffres("tous"),
      ]);
      setOffres(filtered);
      setAllOffres(all);
    } catch {
      notifier("Impossible de charger les offres", "err");
    } finally {
      setLoading(false);
    }
  }, [filtre, notifier]);

  // Setup webhook listeners for real-time updates
  useEffect(() => {
    const unsubscribeNewEmail = webhookClient.on("new_email", () => {
      notifier("📧 Nouvel email reçu", "ok");
      chargerOffres();
    });

    const unsubscribeProcessed = webhookClient.on("email_processed", () => {
      notifier("✨ Email traité par l'IA", "ok");
      chargerOffres();
    });

    // Start polling as fallback
    webhookClient.startPolling(5000);

    return () => {
      unsubscribeNewEmail();
      unsubscribeProcessed();
      webhookClient.stopPolling();
    };
  }, [chargerOffres, notifier]);

  useEffect(() => {
    chargerOffres();
  }, [chargerOffres]);

  const selectionnerOffre = async (resume: Offre) => {
    try {
      const detail = await fetchOffre(resume.id);
      setOffreSelectionnee(detail);
    } catch {
      notifier("Impossible de charger le détail de l'offre", "err");
    }
  };

  const modifierLigne = (
    idx: number,
    champ: keyof LigneOffre,
    valeur: number | string | boolean
  ) => {
    if (!offreSelectionnee) return;
    const lignes = [...offreSelectionnee.lignes];
    const ligne = { ...lignes[idx], [champ]: valeur };
    ligne.prix_total_ht = parseFloat(
      (
        ligne.quantite_boites *
        ligne.prix_unitaire_ht *
        (1 - ligne.remise_pct / 100)
      ).toFixed(2)
    );
    lignes[idx] = ligne;
    const ht = parseFloat(lignes.reduce((s, l) => s + l.prix_total_ht, 0).toFixed(2));
    setOffreSelectionnee({
      ...offreSelectionnee,
      lignes,
      montant_ht: ht,
      montant_tva: parseFloat((ht * 0.2).toFixed(2)),
      montant_ttc: parseFloat((ht * 1.2).toFixed(2)),
      statut: "modifiee",
    });
  };

  const supprimerLigne = (idx: number) => {
    if (!offreSelectionnee) return;
    const lignes = offreSelectionnee.lignes.filter((_, i) => i !== idx);
    const ht = parseFloat(lignes.reduce((s, l) => s + l.prix_total_ht, 0).toFixed(2));
    setOffreSelectionnee({
      ...offreSelectionnee,
      lignes,
      montant_ht: ht,
      montant_tva: parseFloat((ht * 0.2).toFixed(2)),
      montant_ttc: parseFloat((ht * 1.2).toFixed(2)),
      statut: "modifiee",
    });
  };

  const sauvegarder = async () => {
    if (!offreSelectionnee) return;
    setSaving(true);
    try {
      await saveOffre(offreSelectionnee.id, {
        lignes: offreSelectionnee.lignes,
        montant_ht: offreSelectionnee.montant_ht,
        montant_tva: offreSelectionnee.montant_tva,
        montant_ttc: offreSelectionnee.montant_ttc,
        texte_intro: offreSelectionnee.texte_intro,
        texte_conclusion: offreSelectionnee.texte_conclusion,
        statut: offreSelectionnee.statut,
      });
      notifier("Offre sauvegardée", "ok");
      await chargerOffres();
    } catch {
      notifier("Erreur lors de la sauvegarde", "err");
    } finally {
      setSaving(false);
    }
  };

  const validerEtEnvoyer = async () => {
    if (!offreSelectionnee) return;
    setSaving(true);
    try {
      await saveOffre(offreSelectionnee.id, {
        lignes: offreSelectionnee.lignes,
        montant_ht: offreSelectionnee.montant_ht,
        montant_tva: offreSelectionnee.montant_tva,
        montant_ttc: offreSelectionnee.montant_ttc,
        texte_intro: offreSelectionnee.texte_intro,
        texte_conclusion: offreSelectionnee.texte_conclusion,
        statut: offreSelectionnee.statut,
      });
      await validateAndSendOffre(offreSelectionnee.id, offreSelectionnee);
      notifier("Offre validée — DOCX téléchargé", "ok");
      setOffreSelectionnee(null);
      await chargerOffres();
    } catch {
      notifier("Erreur lors de l'envoi ou de la génération DOCX", "err");
    } finally {
      setSaving(false);
    }
  };

  const telechargerDocx = async () => {
    if (!offreSelectionnee) return;
    setSaving(true);
    try {
      await downloadOffreDocument(offreSelectionnee);
      notifier("Offre DOCX téléchargée", "ok");
    } catch {
      notifier("Impossible de générer le DOCX (backend requis)", "err");
    } finally {
      setSaving(false);
    }
  };

  const refuserOffre = async () => {
    if (!offreSelectionnee || !confirm("Confirmer le refus de cette offre ?")) return;
    try {
      await rejectOffre(offreSelectionnee.id);
      notifier("Offre refusée", "ok");
      setOffreSelectionnee(null);
      await chargerOffres();
    } catch {
      notifier("Erreur lors du refus", "err");
    }
  };

  const analyserAvecIA = async () => {
    if (!offreSelectionnee) return;
    setSaving(true);
    try {
      const result = await processEmailIntoQuote(offreSelectionnee.id);
      notifier(`Offre ${result.numero_offre} générée par l'IA`, "ok");
      await chargerOffres();
      const detail = await fetchOffre(result.quote_id);
      setOffreSelectionnee(detail);
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message.replace(/^Agent IA : /, "")
          : "Erreur agent IA";
      notifier(msg.slice(0, 120), "err");
    } finally {
      setSaving(false);
    }
  };

  const mailEnAttente = offreSelectionnee?.numero_offre.startsWith("MAIL-") ?? false;

  const compteurs = allOffres.reduce(
    (acc, o) => {
      acc[o.statut] = (acc[o.statut] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="mx-auto flex h-[665px] w-full max-w-[1440px] flex-col overflow-hidden bg-gray-50 font-sans shadow-lg">
      <header className="flex shrink-0 items-center justify-between bg-[#1A3A5C] px-6 py-3 text-white shadow-md">
        <div className="flex items-center gap-3">
          <div className="rounded bg-[#2E75B6] px-3 py-1 text-xl font-black tracking-widest">
            BOSS
          </div>
          <div>
            <div className="text-xs leading-none text-blue-200">
              Fournitures Industrielles
            </div>
            <div className="text-sm font-medium">Agent IA – Gestion des offres</div>
          </div>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-blue-200">
            {offres.filter((o) => o.statut === "brouillon").length} offre(s) en attente
          </span>
          <button
            type="button"
            onClick={chargerOffres}
            className="rounded bg-blue-700 px-3 py-1.5 text-xs transition hover:bg-blue-600"
          >
            Actualiser
          </button>
        </div>
      </header>

      {notification && (
        <div
          className={`fixed right-4 top-4 z-50 rounded-lg px-4 py-3 text-sm font-medium shadow-lg ${
            notification.type === "ok" ? "bg-green-600 text-white" : "bg-red-600 text-white"
          }`}
        >
          {notification.msg}
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <aside className="flex w-80 shrink-0 flex-col border-r border-gray-200 bg-white">
          <div className="space-y-1 border-b border-gray-100 p-3">
            {(["tous", "brouillon", "modifiee", "validee", "envoyee", "refusee"] as const).map(
              (s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setFiltre(s)}
                  className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition ${
                    filtre === s
                      ? "bg-blue-50 font-medium text-blue-700"
                      : "text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  <span>{s === "tous" ? "Toutes les offres" : STATUT_CONFIG[s].label}</span>
                  {s !== "tous" && compteurs[s] ? (
                    <span className="rounded-full bg-gray-200 px-1.5 py-0.5 text-xs text-gray-700">
                      {compteurs[s]}
                    </span>
                  ) : null}
                </button>
              )
            )}
          </div>

          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="p-6 text-center text-sm text-gray-400">Chargement…</div>
            ) : offres.length === 0 ? (
              <div className="p-6 text-center text-sm text-gray-400">Aucune offre</div>
            ) : (
              offres.map((offre) => (
                <button
                  key={offre.id}
                  type="button"
                  onClick={() => selectionnerOffre(offre)}
                  className={`w-full border-b border-gray-100 p-4 text-left transition hover:bg-blue-50 ${
                    offreSelectionnee?.id === offre.id
                      ? "border-l-4 border-l-blue-500 bg-blue-50"
                      : ""
                  }`}
                >
                  <div className="mb-1 flex items-center justify-between">
                    <span className="font-mono text-xs text-gray-500">{offre.numero_offre}</span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUT_CONFIG[offre.statut].color}`}
                    >
                      {STATUT_CONFIG[offre.statut].label}
                    </span>
                  </div>
                  <div className="truncate text-sm font-medium text-gray-800">
                    {offre.expediteur_nom}
                  </div>
                  <div className="truncate text-xs text-gray-500">{offre.expediteur_email}</div>
                  <div className="mt-2 flex items-center justify-between">
                    <span className="text-xs text-gray-400">{formatDate(offre.created_at)}</span>
                    <span className="text-sm font-semibold text-gray-800">
                      {formatEur(offre.montant_ttc)}
                    </span>
                  </div>
                </button>
              ))
            )}
          </div>
        </aside>

        {offreSelectionnee ? (
          <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
            <div className="flex shrink-0 items-center justify-between border-b border-gray-200 bg-white px-6 py-3">
              <div>
                <h1 className="text-lg font-semibold text-gray-900">
                  {offreSelectionnee.numero_offre}
                </h1>
                <p className="text-sm text-gray-500">
                  De : <span className="font-medium">{offreSelectionnee.expediteur_nom}</span> ·{" "}
                  {offreSelectionnee.expediteur_email}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {mailEnAttente ? (
                  <button
                    type="button"
                    onClick={analyserAvecIA}
                    disabled={saving}
                    className="rounded-lg bg-[#2E75B6] px-5 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-40"
                  >
                    {saving ? "Analyse…" : "Analyser avec IA"}
                  </button>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={telechargerDocx}
                      disabled={saving}
                      className="rounded-lg border border-blue-200 px-4 py-2 text-sm text-blue-700 transition hover:bg-blue-50"
                    >
                      Télécharger DOCX
                    </button>
                    <button
                      type="button"
                      onClick={refuserOffre}
                      className="rounded-lg border border-red-200 px-4 py-2 text-sm text-red-600 transition hover:bg-red-50"
                    >
                      Refuser
                    </button>
                    <button
                      type="button"
                      onClick={sauvegarder}
                      disabled={saving}
                      className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 transition hover:bg-gray-50"
                    >
                      {saving ? "…" : "Sauvegarder"}
                    </button>
                    <button
                      type="button"
                      onClick={validerEtEnvoyer}
                      disabled={saving || offreSelectionnee.statut === "envoyee"}
                      className="rounded-lg bg-green-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-green-700 disabled:opacity-40"
                    >
                      Valider et envoyer
                    </button>
                  </>
                )}
              </div>
            </div>

            <div className="flex min-h-0 flex-1">
              <div className="w-2/5 shrink-0 overflow-y-auto border-r border-gray-200 bg-gray-50 p-5">
                <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400">
                  Mail original client
                </h2>
                <div className="space-y-2 rounded-xl border border-gray-200 bg-white p-4 text-sm">
                  <div className="flex items-center gap-2 border-b border-gray-100 pb-2 text-xs text-gray-400">
                    <span>{formatDate(offreSelectionnee.recu_le)}</span>
                  </div>
                  <p className="text-xs text-gray-400">
                    <span className="font-medium">Objet :</span> {offreSelectionnee.sujet}
                  </p>
                  <div className="whitespace-pre-wrap pt-1 text-xs leading-relaxed text-gray-700">
                    {offreSelectionnee.corps_email}
                  </div>
                </div>

                {offreSelectionnee.tokens_utilises ? (
                  <div className="mt-4 rounded-xl border border-gray-200 bg-white p-4">
                    <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400">
                      Métriques IA (Langfuse)
                    </h3>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div className="rounded-lg bg-purple-50 p-2 text-center">
                        <div className="text-base font-semibold text-purple-700">
                          {offreSelectionnee.tokens_utilises.toLocaleString("fr-FR")}
                        </div>
                        <div className="text-purple-500">tokens</div>
                      </div>
                      <div className="rounded-lg bg-blue-50 p-2 text-center">
                        <div className="text-base font-semibold text-blue-700">
                          ${offreSelectionnee.cout_usd?.toFixed(4)}
                        </div>
                        <div className="text-blue-500">coût</div>
                      </div>
                      <div className="rounded-lg bg-green-50 p-2 text-center">
                        <div className="text-base font-semibold text-green-700">
                          {offreSelectionnee.latence_ms} ms
                        </div>
                        <div className="text-green-500">latence</div>
                      </div>
                      {offreSelectionnee.langfuse_trace_id && (
                        <a
                          href={`https://cloud.langfuse.com/trace/${offreSelectionnee.langfuse_trace_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="rounded-lg bg-amber-50 p-2 text-center transition hover:bg-amber-100"
                        >
                          <div className="text-base font-semibold text-amber-700">↗</div>
                          <div className="text-amber-500">Langfuse</div>
                        </a>
                      )}
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="min-w-0 flex-1 space-y-4 overflow-y-auto p-5">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                  Offre de prix — éditable
                </h2>

                <div className="rounded-xl border border-gray-200 bg-white p-4">
                  <label className="mb-1 block text-xs font-medium text-gray-500">
                    Texte d&apos;introduction
                  </label>
                  <textarea
                    value={offreSelectionnee.texte_intro}
                    onChange={(e) =>
                      setOffreSelectionnee({
                        ...offreSelectionnee,
                        texte_intro: e.target.value,
                        statut: "modifiee",
                      })
                    }
                    className="w-full resize-none border-none text-sm leading-relaxed text-gray-700 outline-none"
                    rows={3}
                  />
                </div>

                <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
                  <div className="flex items-center justify-between border-b border-gray-100 bg-gray-50 px-4 py-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                      Lignes de l&apos;offre ({offreSelectionnee.lignes.length})
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${STATUT_CONFIG[offreSelectionnee.statut].color}`}
                    >
                      {STATUT_CONFIG[offreSelectionnee.statut].label}
                    </span>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead className="bg-[#1A3A5C] text-white">
                        <tr>
                          {[
                            "Réf.",
                            "Désignation",
                            "Alliage",
                            "Qté boîtes",
                            "Prix unit. HT",
                            "Remise %",
                            "Total HT",
                            "Stock",
                            "Délai",
                            "Conf.",
                            "",
                          ].map((h) => (
                            <th
                              key={h || "actions"}
                              className="whitespace-nowrap px-3 py-2 text-left text-xs font-medium"
                            >
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {offreSelectionnee.lignes.map((ligne, idx) => (
                          <tr
                            key={`${ligne.reference}-${idx}`}
                            className={`border-b border-gray-100 transition hover:bg-blue-50 ${
                              idx % 2 ? "bg-gray-50" : "bg-white"
                            }`}
                          >
                            <td className="whitespace-nowrap px-3 py-2 font-mono text-gray-600">
                              {ligne.reference}
                            </td>
                            <td className="max-w-[180px] px-3 py-2 text-gray-700">
                              <div className="truncate" title={ligne.designation}>
                                {ligne.designation}
                              </div>
                              <div
                                className="truncate text-xs italic text-gray-400"
                                title={ligne.description_originale_client}
                              >
                                → {ligne.description_originale_client}
                              </div>
                              <div className="text-[10px] text-gray-400">
                                Cdt/boîte : {ligne.conditionnement}
                              </div>
                            </td>
                            <td className="whitespace-nowrap px-3 py-2 text-gray-600">
                              {ligne.alliage}
                            </td>
                            <td className="px-3 py-2">
                              <input
                                type="number"
                                min={1}
                                value={ligne.quantite_boites}
                                onChange={(e) =>
                                  modifierLigne(
                                    idx,
                                    "quantite_boites",
                                    parseInt(e.target.value, 10) || 1
                                  )
                                }
                                className="w-14 rounded border border-gray-200 px-1 py-0.5 text-center text-xs"
                              />
                            </td>
                            <td className="px-3 py-2">
                              <input
                                type="number"
                                min={0}
                                step={0.01}
                                value={ligne.prix_unitaire_ht}
                                onChange={(e) =>
                                  modifierLigne(
                                    idx,
                                    "prix_unitaire_ht",
                                    parseFloat(e.target.value) || 0
                                  )
                                }
                                className="w-20 rounded border border-gray-200 px-1 py-0.5 text-right text-xs"
                              />
                            </td>
                            <td className="px-3 py-2">
                              <input
                                type="number"
                                min={0}
                                max={100}
                                step={0.5}
                                value={ligne.remise_pct}
                                onChange={(e) =>
                                  modifierLigne(
                                    idx,
                                    "remise_pct",
                                    parseFloat(e.target.value) || 0
                                  )
                                }
                                className="w-14 rounded border border-gray-200 px-1 py-0.5 text-center text-xs"
                              />
                            </td>
                            <td className="whitespace-nowrap px-3 py-2 text-right font-semibold text-gray-800">
                              {formatEur(ligne.prix_total_ht)}
                            </td>
                            <td className="px-3 py-2 text-center">
                              <span
                                className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                                  ligne.en_stock
                                    ? "bg-green-100 text-green-700"
                                    : "bg-red-100 text-red-700"
                                }`}
                              >
                                {ligne.en_stock ? "Oui" : "Non"}
                              </span>
                            </td>
                            <td className="whitespace-nowrap px-3 py-2 text-center text-gray-600">
                              {ligne.delai_livraison}
                            </td>
                            <td className="whitespace-nowrap px-3 py-2 text-center text-gray-600">
                              {ligne.conditionnement}
                            </td>
                            <td className="px-3 py-2 text-center">
                              <button
                                type="button"
                                onClick={() => supprimerLigne(idx)}
                                className="text-red-600 transition hover:text-red-800"
                              >
                                ✕
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="rounded-xl border border-gray-200 bg-white p-4">
                  <label className="mb-1 block text-xs font-medium text-gray-500">
                    Texte de conclusion
                  </label>
                  <textarea
                    value={offreSelectionnee.texte_conclusion}
                    onChange={(e) =>
                      setOffreSelectionnee({
                        ...offreSelectionnee,
                        texte_conclusion: e.target.value,
                        statut: "modifiee",
                      })
                    }
                    className="w-full resize-none border-none text-sm leading-relaxed text-gray-700 outline-none"
                    rows={3}
                  />
                </div>

                <div className="rounded-xl border border-gray-200 bg-white p-4">
                  <div className="grid grid-cols-3 gap-4 text-center">
                    <div>
                      <div className="text-xs text-gray-500">Montant HT</div>
                      <div className="text-lg font-semibold text-gray-900">
                        {formatEur(offreSelectionnee.montant_ht)}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-500">TVA (20%)</div>
                      <div className="text-lg font-semibold text-gray-900">
                        {formatEur(offreSelectionnee.montant_tva)}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-500">Montant TTC</div>
                      <div className="text-lg font-semibold text-blue-700">
                        {formatEur(offreSelectionnee.montant_ttc)}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </main>
        ) : (
          <div className="flex min-w-0 flex-1 items-center justify-center bg-gray-50">
            <div className="text-center text-gray-400">
              <div className="text-lg font-medium">Sélectionnez une offre</div>
              <div className="text-sm">pour voir les détails</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

