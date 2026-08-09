"use client";

import type { EntityType } from "@hushmark/shared";
import { useTranslations } from "next-intl";
import { useEffect, useState, type SyntheticEvent } from "react";

import { PageHead } from "@/components/page-head";
import {
  adminJson,
  makePolicyInput,
  matrixRows,
  policyActions,
  type EnterprisePolicy,
  type PolicyAction,
} from "@/lib/admin";

const classes = ["general", "special", "secret"] as const;

export function PolicyMatrix() {
  const t = useTranslations("Policies");
  const common = useTranslations("Common");
  const [actions, setActions] = useState<Record<EntityType, PolicyAction>>(() =>
    policyActions(undefined),
  );
  const [name, setName] = useState("");
  const [priority, setPriority] = useState(100);
  const [policyId, setPolicyId] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<"saved" | "invalid" | null>(null);

  useEffect(() => {
    void adminJson<EnterprisePolicy[]>("policies").then((policies) => {
      const current = policies[0];
      if (current === undefined) return;
      setPolicyId(current.id);
      setName(current.name);
      setPriority(current.priority);
      setActions(policyActions(current));
    });
  }, []);

  async function save(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setMessage(null);
    try {
      const input = makePolicyInput(name, priority, actions);
      const saved = await adminJson<EnterprisePolicy>(
        policyId === null ? "policies" : `policies/${policyId}`,
        {
          method: policyId === null ? "POST" : "PUT",
          body: JSON.stringify(input),
        },
      );
      setPolicyId(saved.id);
      setMessage("saved");
    } catch {
      setMessage("invalid");
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <PageHead eyebrow={t("eyebrow")} subtitle={t("subtitle")} title={t("title")} />
      <form className="card" onSubmit={(event) => void save(event)}>
        <div className="form-grid">
          <label>
            {t("name")}
            <input
              name="policy-name"
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label>
            {t("priority")}
            <input
              name="policy-priority"
              required
              type="number"
              value={priority}
              onChange={(event) => setPriority(event.target.valueAsNumber)}
            />
          </label>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t("entity")}</th>
                <th>{t("class")}</th>
                <th>{t("action")}</th>
              </tr>
            </thead>
            <tbody>
              {classes.flatMap((kvkkClass) => [
                <tr className="matrix-group" key={`${kvkkClass}-heading`}>
                  <td colSpan={3}>{t(kvkkClass)}</td>
                </tr>,
                ...matrixRows
                  .filter((row) => row.kvkk_class === kvkkClass)
                  .map((row) => (
                    <tr key={row.type}>
                      <td>
                        <strong>{row.tr_label}</strong>
                        <br />
                        <span className="matrix-code">{row.type}</span>
                      </td>
                      <td>
                        <span className="pill">{row.z_class}</span>
                      </td>
                      <td>
                        <select
                          aria-label={`${row.type} ${t("action")}`}
                          value={actions[row.type]}
                          onChange={(event) =>
                            setActions((current) => ({
                              ...current,
                              [row.type]: event.target.value as PolicyAction,
                            }))
                          }
                        >
                          <option value="allow">{t("allow")}</option>
                          <option value="mask">{t("mask")}</option>
                          <option value="block">{t("block")}</option>
                        </select>
                      </td>
                    </tr>
                  )),
              ])}
            </tbody>
          </table>
        </div>
        <div className="form-actions">
          <button className="button" disabled={pending} type="submit">
            {pending ? common("saving") : common("save")}
          </button>
          {message === "saved" ? <span className="success-notice">{t("saved")}</span> : null}
          {message === "invalid" ? <span className="error-notice">{t("invalid")}</span> : null}
        </div>
      </form>
    </>
  );
}
