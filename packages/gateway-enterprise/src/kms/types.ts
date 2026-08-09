export interface Kms {
  wrap(keyId: string, dataKey: Uint8Array): Promise<string>;
  unwrap(keyId: string, wrappedKey: string): Promise<Uint8Array>;
}
