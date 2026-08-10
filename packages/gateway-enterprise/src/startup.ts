export interface StartupRetryOptions {
  attempts: number;
  delayMs: number;
  sleep?: (delayMs: number) => Promise<void>;
}

export async function retryStartup<T>(
  operation: () => Promise<T>,
  options: StartupRetryOptions,
): Promise<T> {
  const sleep =
    options.sleep ?? ((delayMs: number) => new Promise((resolve) => setTimeout(resolve, delayMs)));
  let lastError: unknown;
  for (let attempt = 1; attempt <= options.attempts; attempt += 1) {
    try {
      return await operation();
    } catch (error) {
      lastError = error;
      if (attempt === options.attempts) throw error;
      await sleep(options.delayMs);
    }
  }
  throw lastError;
}
