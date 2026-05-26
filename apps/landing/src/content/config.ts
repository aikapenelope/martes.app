import { defineCollection, z } from 'astro:content';

const docs = defineCollection({
  type: 'content',
  schema: z.object({
    title:       z.string(),
    description: z.string().optional(),
    order:       z.number().default(99),
    section:     z.string().default('General'),
  }),
});

const blog = defineCollection({
  type: 'content',
  schema: z.object({
    title:       z.string(),
    description: z.string(),
    date:        z.string(),        // ISO 8601: "2026-06-04"
    tags:        z.array(z.string()).default([]),
    author:      z.string().default('martes.app'),
  }),
});

export const collections = { docs, blog };
