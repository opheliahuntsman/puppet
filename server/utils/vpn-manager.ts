import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export interface VPNConfig {
  enabled: boolean;
  command: string;
  connectionVerifyUrl: string;
  connectionVerifyTimeout: number;
  maxRetries: number;
  retryDelay: number;
}

export class VPNManager {
  private config: VPNConfig;
  private isConnected: boolean = false;

  constructor(config: VPNConfig) {
    this.config = config;
  }

  async changeVPN(): Promise<void> {
    if (!this.config.enabled || !this.config.command) {
      console.log('VPN rotation is disabled or no command configured');
      return;
    }

    console.log('\n' + '='.repeat(60));
    console.log('VPN ROTATION REQUESTED');
    console.log('='.repeat(60));
    console.log(`Command: ${this.config.command}`);
    console.log('Please execute the VPN change command in your terminal.');
    console.log('Waiting for VPN connection to be established...');
    console.log('='.repeat(60) + '\n');

    // If user provided a command, attempt to execute it
    if (this.config.command && this.config.command !== 'manual') {
      try {
        console.log(`Executing VPN command: ${this.config.command}`);
        const { stdout, stderr } = await execAsync(this.config.command);
        
        if (stdout) {
          console.log('VPN Command Output:', stdout);
        }
        if (stderr) {
          console.warn('VPN Command Warnings:', stderr);
        }
        
        console.log('✅ VPN command executed successfully');
      } catch (error) {
        console.error('❌ VPN command execution failed:', error instanceof Error ? error.message : error);
        console.log('Please manually change your VPN connection');
      }
    }

    // Wait for connection to be established
    await this.waitForConnection();
  }

  async waitForConnection(): Promise<void> {
    console.log('\n⏳ Verifying VPN connection...');
    
    let attempts = 0;
    const maxAttempts = this.config.maxRetries || 10;
    
    while (attempts < maxAttempts) {
      attempts++;
      
      try {
        // Simple connection check using fetch to verify URL
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.config.connectionVerifyTimeout || 5000);
        
        const response = await fetch(this.config.connectionVerifyUrl || 'https://www.google.com', {
          signal: controller.signal,
          method: 'HEAD'
        });
        
        clearTimeout(timeoutId);
        
        if (response.ok) {
          console.log(`✅ Connection verified (attempt ${attempts}/${maxAttempts})`);
          this.isConnected = true;
          
          // Get and display current IP for verification
          try {
            const ipResponse = await fetch('https://api.ipify.org?format=json');
            const ipData = await ipResponse.json();
            console.log(`📍 Current IP: ${ipData.ip}`);
          } catch (ipError) {
            // Ignore IP fetch errors
          }
          
          return;
        }
      } catch (error) {
        console.log(`⚠️  Connection check failed (attempt ${attempts}/${maxAttempts})`);
      }
      
      if (attempts < maxAttempts) {
        const delay = this.config.retryDelay || 2000;
        console.log(`⏳ Waiting ${delay}ms before next connection check...`);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
    
    throw new Error(`Failed to verify VPN connection after ${maxAttempts} attempts. Please check your VPN connection manually.`);
  }

  async ensureConnection(): Promise<void> {
    if (!this.config.enabled) {
      return;
    }

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000);
      
      const response = await fetch(this.config.connectionVerifyUrl || 'https://www.google.com', {
        signal: controller.signal,
        method: 'HEAD'
      });
      
      clearTimeout(timeoutId);
      this.isConnected = response.ok;
    } catch (error) {
      this.isConnected = false;
      console.warn('⚠️  Connection check failed, may need VPN rotation');
    }
  }

  isVPNConnected(): boolean {
    return this.isConnected;
  }

  static createDefaultConfig(): VPNConfig {
    return {
      enabled: false,
      command: 'manual',
      connectionVerifyUrl: 'https://www.google.com',
      connectionVerifyTimeout: 5000,
      maxRetries: 10,
      retryDelay: 2000
    };
  }
}
