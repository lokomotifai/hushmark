import { z } from "zod";

import { ENTITY_TYPES } from "./taxonomy.gen.js";

export const LanguageSchema = z.enum(["tr", "en"]);
export const LayerSchema = z.enum(["deterministic", "ner"]);
export const EntityTypeSchema = z.enum(ENTITY_TYPES);

export const TextItemSchema = z
  .object({
    id: z.string().min(1),
    text: z.string(),
  })
  .strict();

export const AnalyzeRequestSchema = z
  .object({
    items: z.array(TextItemSchema).min(1),
    language: LanguageSchema.default("tr"),
    session: z.string().optional(),
  })
  .strict();

export const EntitySpanSchema = z
  .object({
    type: EntityTypeSchema,
    start: z.number().int().nonnegative(),
    end: z.number().int().positive(),
    confidence: z.number().min(0).max(1),
    layer: LayerSchema,
  })
  .strict();

export const MappingSchema = EntitySpanSchema.extend({
  placeholder: z.string(),
  value: z.string().optional(),
}).strict();

export const AnalyzeResponseSchema = z
  .object({
    items: z.array(
      z
        .object({
          id: z.string(),
          entities: z.array(EntitySpanSchema),
        })
        .strict(),
    ),
    model_id: z.string(),
    taxonomy_version: z.string(),
  })
  .strict();

export const MaskRequestSchema = AnalyzeRequestSchema.extend({
  include_values: z.boolean().default(false),
  collision_mode: z.enum(["reject", "prefix"]).default("reject"),
}).strict();

export const MaskResponseSchema = z
  .object({
    items: z.array(
      z
        .object({
          id: z.string(),
          masked_text: z.string(),
          mappings: z.array(MappingSchema),
        })
        .strict(),
    ),
    model_id: z.string(),
    taxonomy_version: z.string(),
  })
  .strict();

export type AnalyzeRequest = z.infer<typeof AnalyzeRequestSchema>;
export type AnalyzeResponse = z.infer<typeof AnalyzeResponseSchema>;
export type MaskRequest = z.infer<typeof MaskRequestSchema>;
export type MaskResponse = z.infer<typeof MaskResponseSchema>;
