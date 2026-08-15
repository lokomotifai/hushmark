import { createRequire } from "node:module";

import { Document, Font, Page, StyleSheet, Text, View, renderToBuffer } from "@react-pdf/renderer";

import type { AuditRecord } from "../audit/types.js";
import { verifyAuditChain, type VerifyResult } from "../audit/verify.js";

const require = createRequire(import.meta.url);

Font.register({
  family: "DejaVu Sans",
  fonts: [
    {
      src: require.resolve("dejavu-fonts-ttf/ttf/DejaVuSans.ttf"),
      fontWeight: 400,
    },
    {
      src: require.resolve("dejavu-fonts-ttf/ttf/DejaVuSans-Bold.ttf"),
      fontWeight: 600,
    },
    {
      src: require.resolve("dejavu-fonts-ttf/ttf/DejaVuSans-Bold.ttf"),
      fontWeight: 700,
    },
  ],
});
Font.registerHyphenationCallback((word) => [word]);

export interface TedbirReportData {
  period: { from: string; to: string };
  generatedAt: string;
  totals: {
    events: number;
    masked: number;
    blocked: number;
    vaultResolves: number;
    policyChanges: number;
  };
  entities: { type: string; count: number }[];
  chain: { ok: boolean; verified: number; firstBrokenSeq: number | null };
}

export function buildTedbirReportData(
  records: readonly AuditRecord[],
  from: string,
  to: string,
  generatedAt = new Date().toISOString(),
  verify: (
    records: readonly AuditRecord[],
    from: number,
    to: number | "latest",
  ) => VerifyResult = verifyAuditChain,
): TedbirReportData {
  const fromMs = Date.parse(`${from}T00:00:00.000Z`);
  const toMs = Date.parse(`${to}T23:59:59.999Z`);
  if (!Number.isFinite(fromMs) || !Number.isFinite(toMs) || fromMs > toMs) {
    throw new RangeError("invalid report period");
  }
  const selected = records.filter((record) => {
    const instant = Date.parse(record.ts);
    return instant >= fromMs && instant <= toMs;
  });
  const entityCounts = new Map<string, number>();
  for (const record of selected) {
    for (const entity of record.entities) {
      entityCounts.set(entity.type, (entityCounts.get(entity.type) ?? 0) + entity.count);
    }
  }
  const rangeStart = selected.at(0)?.seq ?? 1;
  const rangeEnd = selected.at(-1)?.seq ?? "latest";
  const chain = verify(records, rangeStart, rangeEnd);
  return {
    period: { from, to },
    generatedAt,
    totals: {
      events: selected.length,
      masked: selected.reduce(
        (total, record) =>
          total +
          record.entities
            .filter((entity) => entity.action === "mask")
            .reduce((sum, entity) => sum + entity.count, 0),
        0,
      ),
      blocked: selected.filter((record) => record.kind === "REQUEST_BLOCKED").length,
      vaultResolves: selected.filter((record) => record.kind === "VAULT_RESOLVE").length,
      policyChanges: selected.filter((record) => record.kind === "POLICY_CHANGED").length,
    },
    entities: [...entityCounts.entries()]
      .map(([type, count]) => ({ type, count }))
      .sort((left, right) => right.count - left.count || left.type.localeCompare(right.type)),
    chain,
  };
}

export async function renderTedbirPdf(data: TedbirReportData): Promise<Buffer> {
  return renderToBuffer(<TedbirReportDocument data={data} />);
}

export function TedbirReportDocument({ data }: { data: TedbirReportData }) {
  return (
    <Document
      author="Hushmark"
      subject="KVKK Madde 12 teknik tedbir dönem raporu"
      title="Hushmark Teknik Tedbir Raporu"
    >
      <Page size="A4" style={styles.page}>
        <View style={styles.hero}>
          <Text style={styles.kicker}>HUSHMARK / DÖNEMSEL KANIT</Text>
          <Text style={styles.title}>KVKK Madde 12 Teknik Tedbir Raporu</Text>
          <Text style={styles.period}>
            {formatDate(data.period.from)} - {formatDate(data.period.to)}
          </Text>
          <Text style={styles.generated}>Üretim: {formatInstant(data.generatedAt)}</Text>
        </View>

        <Section title="Dönem Özeti">
          <View style={styles.metricGrid}>
            <Metric label="Denetim olayı" value={data.totals.events} />
            <Metric label="Maskelenen alan" value={data.totals.masked} />
            <Metric label="Engellenen istek" value={data.totals.blocked} />
            <Metric label="Yetkili çözümleme" value={data.totals.vaultResolves} />
          </View>
        </Section>

        <Section title="Teknik Tedbir Eşlemesi">
          <TableHeader columns={["Teknik alan", "Uygulanan tedbir", "Dönem kanıtı"]} />
          <MeasureRow
            area="Veri Maskeleme"
            measure="Tespit edilen alanların sağlayıcıya gitmeden yer tutucularla değiştirilmesi"
            evidence={`${String(data.totals.masked)} maskelenen alan`}
          />
          <MeasureRow
            area="Şifreleme/Anahtar Yönetimi"
            measure="Oturum veri anahtarlarının KMS ile zarf şifreleme altında tutulması"
            evidence={`${String(data.totals.vaultResolves)} yetkili çözümleme`}
          />
          <MeasureRow
            area="Log Kayıtları"
            measure="İçerik değeri taşımayan, birbirine bağlı denetim olayları"
            evidence={`${String(data.totals.events)} zincir olayı`}
          />
          <MeasureRow
            area="Yetki Matrisi"
            measure="Yönetici, operatör ve denetçi rolleriyle sınırlandırılmış işlemler"
            evidence={`${String(data.totals.policyChanges)} politika değişikliği`}
          />
        </Section>

        <Section title="Varlık Türü Dağılımı">
          {data.entities.length === 0 ? (
            <Text style={styles.muted}>Seçilen dönemde varlık sayımı bulunmuyor.</Text>
          ) : (
            <View style={styles.tags}>
              {data.entities.map((entity) => (
                <View key={entity.type} style={styles.tag}>
                  <Text style={styles.tagName}>{entity.type}</Text>
                  <Text style={styles.tagCount}>{entity.count}</Text>
                </View>
              ))}
            </View>
          )}
        </Section>

        <Section title="Denetim Kaydı Doğrulaması">
          <View style={data.chain.ok ? styles.statusOk : styles.statusError}>
            <Text style={styles.statusTitle}>
              {data.chain.ok ? "Zincir doğrulandı" : "Zincir bütünlüğü doğrulanamadı"}
            </Text>
            <Text style={styles.statusBody}>
              {data.chain.ok
                ? `${String(data.chain.verified)} kayıt sıra ve özet bağlantılarıyla doğrulandı.`
                : `İlk tutarsız kayıt: ${String(data.chain.firstBrokenSeq ?? "bilinmiyor")}.`}
            </Text>
          </View>
        </Section>

        <Section title="Kapsam ve Sınırlar">
          <Text style={styles.body}>
            Bu rapor, seçilen dönemde Hushmark tarafından kaydedilen teknik tedbir sinyallerinin
            özetidir. Hukuki uygunluk görüşü değildir; kurumun süreç, insan, tedarikçi ve fiziksel
            güvenlik kontrolleri ayrıca değerlendirilmelidir. İstatistikler yalnızca denetim
            zincirinde bulunan olaylardan üretilir ve ham kişisel veri içermez.
          </Text>
        </Section>

        <View style={styles.footer}>
          <Text>Hushmark / Teknik tedbir kanıtı</Text>
          <Text>1 / 1</Text>
        </View>
      </Page>
    </Document>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section} wrap={false}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {children}
    </View>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricValue}>{value}</Text>
      <Text style={styles.metricLabel}>{label}</Text>
    </View>
  );
}

function TableHeader({ columns }: { columns: [string, string, string] }) {
  return (
    <View style={[styles.row, styles.tableHeader]}>
      <Text style={[styles.cell, styles.cellArea]}>{columns[0]}</Text>
      <Text style={[styles.cell, styles.cellMeasure]}>{columns[1]}</Text>
      <Text style={[styles.cell, styles.cellEvidence]}>{columns[2]}</Text>
    </View>
  );
}

function MeasureRow({
  area,
  measure,
  evidence,
}: {
  area: string;
  measure: string;
  evidence: string;
}) {
  return (
    <View style={styles.row} wrap={false}>
      <Text style={[styles.cell, styles.cellArea, styles.strong]}>{area}</Text>
      <Text style={[styles.cell, styles.cellMeasure]}>{measure}</Text>
      <Text style={[styles.cell, styles.cellEvidence]}>{evidence}</Text>
    </View>
  );
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("tr-TR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00.000Z`));
}

function formatInstant(value: string): string {
  return new Intl.DateTimeFormat("tr-TR", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}

const palette = {
  ink: "#17211c",
  muted: "#59665f",
  forest: "#175c45",
  mint: "#dcece5",
  mist: "#f4f7f5",
  line: "#ced8d2",
  coral: "#b24c3e",
  coralLight: "#f7e7e3",
};

const styles = StyleSheet.create({
  page: {
    paddingTop: 36,
    paddingRight: 40,
    paddingBottom: 44,
    paddingLeft: 40,
    color: palette.ink,
    fontFamily: "DejaVu Sans",
    fontSize: 8.5,
    lineHeight: 1.45,
  },
  hero: {
    padding: 22,
    borderRadius: 8,
    backgroundColor: palette.forest,
    color: "#ffffff",
    marginBottom: 18,
  },
  kicker: { fontSize: 7, letterSpacing: 1.3, fontWeight: 700, marginBottom: 8 },
  title: { fontSize: 21, lineHeight: 1.12, fontWeight: 700, maxWidth: 390 },
  period: { fontSize: 10, fontWeight: 600, marginTop: 12 },
  generated: { fontSize: 7.5, marginTop: 3, color: "#d8ebe3" },
  section: { marginBottom: 14 },
  sectionTitle: {
    color: palette.forest,
    fontSize: 11,
    fontWeight: 700,
    marginBottom: 7,
  },
  metricGrid: { flexDirection: "row", gap: 7 },
  metric: {
    flexGrow: 1,
    flexBasis: 0,
    padding: 10,
    borderRadius: 5,
    backgroundColor: palette.mist,
  },
  metricValue: { color: palette.forest, fontSize: 16, fontWeight: 700 },
  metricLabel: { color: palette.muted, fontSize: 7, marginTop: 2 },
  row: { flexDirection: "row", borderBottomWidth: 0.7, borderBottomColor: palette.line },
  tableHeader: { color: "#ffffff", backgroundColor: palette.forest, fontWeight: 700 },
  cell: { paddingTop: 6, paddingRight: 6, paddingBottom: 6, paddingLeft: 6 },
  cellArea: { width: "25%" },
  cellMeasure: { width: "49%" },
  cellEvidence: { width: "26%" },
  strong: { fontWeight: 600 },
  tags: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  tag: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingTop: 5,
    paddingRight: 8,
    paddingBottom: 5,
    paddingLeft: 8,
    borderRadius: 99,
    backgroundColor: palette.mint,
  },
  tagName: { color: palette.forest, fontSize: 7, fontWeight: 600 },
  tagCount: { color: palette.ink, fontSize: 7, fontWeight: 700 },
  statusOk: {
    padding: 11,
    borderLeftWidth: 3,
    borderLeftColor: palette.forest,
    backgroundColor: palette.mint,
  },
  statusError: {
    padding: 11,
    borderLeftWidth: 3,
    borderLeftColor: palette.coral,
    backgroundColor: palette.coralLight,
  },
  statusTitle: { fontWeight: 700, marginBottom: 2 },
  statusBody: { color: palette.muted },
  body: { color: palette.muted, lineHeight: 1.55 },
  muted: { color: palette.muted },
  footer: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: "auto",
    paddingTop: 6,
    borderTopWidth: 0.7,
    borderTopColor: palette.line,
    color: palette.muted,
    fontSize: 6.5,
  },
});
