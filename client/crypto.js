const CRYPTO = {
  _keyPair: null,
  _privateKey: null,

  async generateKeyPair() {
    const keyPair = await crypto.subtle.generateKey(
      { name: "ECDH", namedCurve: "P-256" },
      true,
      ["deriveKey", "deriveBits"]
    );
    this._keyPair = keyPair;
    this._privateKey = keyPair.privateKey;
    await this._savePrivateKey(keyPair.privateKey);
    return keyPair;
  },

  async _savePrivateKey(privateKey) {
    const raw = await crypto.subtle.exportKey("pkcs8", privateKey);
    localStorage.setItem("private_key", this._arrayBufferToHex(raw));
    const pub = await crypto.subtle.exportKey("raw", this._keyPair.publicKey);
    localStorage.setItem("public_key", this._arrayBufferToHex(pub));
  },

  async loadPrivateKey() {
    const privHex = localStorage.getItem("private_key");
    const pubHex = localStorage.getItem("public_key");
    if (!privHex || !pubHex) return false;
    try {
      const privRaw = this._hexToArrayBuffer(privHex);
      const privKey = await crypto.subtle.importKey(
        "pkcs8", privRaw,
        { name: "ECDH", namedCurve: "P-256" },
        true, ["deriveKey", "deriveBits"]
      );
      const pubRaw = this._hexToArrayBuffer(pubHex);
      const pubKey = await crypto.subtle.importKey(
        "raw", pubRaw,
        { name: "ECDH", namedCurve: "P-256" },
        true, []
      );
      this._privateKey = privKey;
      this._keyPair = { privateKey: privKey, publicKey: pubKey };
      return true;
    } catch { return false; }
  },

  async exportPublicKey() {
    if (!this._keyPair) throw new Error("No key pair generated");
    const raw = await crypto.subtle.exportKey("raw", this._keyPair.publicKey);
    return this._arrayBufferToHex(raw);
  },

  async importPublicKey(hex) {
    const raw = this._hexToArrayBuffer(hex);
    return crypto.subtle.importKey(
      "raw", raw,
      { name: "ECDH", namedCurve: "P-256" },
      true, []
    );
  },

  async deriveSharedKey(theirPublicKey) {
    const shared = await crypto.subtle.deriveBits(
      { name: "ECDH", public: theirPublicKey },
      this._privateKey,
      256
    );
    return crypto.subtle.importKey(
      "raw", shared,
      { name: "AES-GCM" },
      false, ["encrypt", "decrypt"]
    );
  },

  async encryptMessage(plaintext, recipientPublicKeyHex) {
    const theirKey = await this.importPublicKey(recipientPublicKeyHex);
    const sharedKey = await this.deriveSharedKey(theirKey);
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const encoded = new TextEncoder().encode(plaintext);
    const ciphertext = await crypto.subtle.encrypt(
      { name: "AES-GCM", iv },
      sharedKey,
      encoded
    );
    const salt = crypto.getRandomValues(new Uint8Array(16));
    return {
      ciphertext: this._arrayBufferToHex(ciphertext),
      iv: this._arrayBufferToHex(iv),
      salt: this._arrayBufferToHex(salt),
    };
  },

  async decryptMessage(ciphertextHex, ivHex, recipientPublicKeyHex) {
    const theirKey = await this.importPublicKey(recipientPublicKeyHex);
    const sharedKey = await this.deriveSharedKey(theirKey);
    const ciphertext = this._hexToArrayBuffer(ciphertextHex);
    const iv = this._hexToArrayBuffer(ivHex);
    const decrypted = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv },
      sharedKey,
      ciphertext
    );
    return new TextDecoder().decode(decrypted);
  },

  async hashFile(file) {
    const buffer = await file.arrayBuffer();
    const hash = await crypto.subtle.digest("SHA-256", buffer);
    return this._arrayBufferToHex(hash);
  },

  async encryptFile(file) {
    const key = await crypto.subtle.generateKey(
      { name: "AES-GCM", length: 256 },
      true,
      ["encrypt"]
    );
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const plaintext = await file.arrayBuffer();
    const ciphertext = await crypto.subtle.encrypt(
      { name: "AES-GCM", iv },
      key,
      plaintext
    );
    const rawKey = await crypto.subtle.exportKey("raw", key);
    return {
      encryptedBlob: new Blob([ciphertext], { type: file.type }),
      iv: this._arrayBufferToHex(iv),
      key: this._arrayBufferToHex(rawKey),
      plaintextHash: await this.hashFile(file),
      filename: file.name,
      mimeType: file.type,
      size: plaintext.byteLength,
    };
  },

  _arrayBufferToHex(buf) {
    return Array.from(new Uint8Array(buf))
      .map(b => b.toString(16).padStart(2, "0"))
      .join("");
  },

  _hexToArrayBuffer(hex) {
    const bytes = new Uint8Array(hex.length / 2);
    for (let i = 0; i < hex.length; i += 2) {
      bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
    }
    return bytes.buffer;
  }
};
