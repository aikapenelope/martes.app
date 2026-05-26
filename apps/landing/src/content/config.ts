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

export const collections = { docs };
