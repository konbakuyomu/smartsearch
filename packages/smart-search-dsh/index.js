import { defineTool } from '@deepseek-ai/dsh-tools'
import { registerSmartSearchTools } from './src/tools.js'

export const name = 'smart-search-dsh'
export const inject = ['tools']

export async function apply(ctx, config = {}) {
  registerSmartSearchTools(ctx, config, defineTool)
}
