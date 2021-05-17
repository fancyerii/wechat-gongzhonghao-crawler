package com.github.fancyerii.wechatcrawler.server.tool;

import spark.Request;

import javax.crypto.*;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.PBEKeySpec;
import javax.crypto.spec.SecretKeySpec;
import java.io.UnsupportedEncodingException;
import java.security.InvalidAlgorithmParameterException;
import java.security.InvalidKeyException;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.security.spec.InvalidKeySpecException;
import java.security.spec.KeySpec;
import java.util.Base64;

public class Tool {
    public static String getIp(Request req) {
        String ipAddress = req.headers("X-FORWARDED-FOR");
        if (ipAddress == null) {
            ipAddress = req.ip();
        }
        return ipAddress;
    }

    public static SecretKey getKeyFromPassword(String password, String salt)
            throws NoSuchAlgorithmException, InvalidKeySpecException, UnsupportedEncodingException {

        SecretKeyFactory factory = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256");
        KeySpec spec = new PBEKeySpec(password.toCharArray(), salt.getBytes("UTF-8"), 65536, 256);
        SecretKey secret = new SecretKeySpec(factory.generateSecret(spec)
                .getEncoded(), "AES");
        return secret;
    }

    public static IvParameterSpec generateIv() {
        byte[] iv = new byte[16];
        new SecureRandom().nextBytes(iv);
        return new IvParameterSpec(iv);
    }

    public static String generateIvBase64() {
        byte[] iv = new byte[16];
        new SecureRandom().nextBytes(iv);
        return Base64.getEncoder().encodeToString(iv);
    }

    public static IvParameterSpec getIvFromBase64(String s) {
        byte[] iv = Base64.getDecoder().decode(s);
        return new IvParameterSpec(iv);
    }

    public static String encrypt(String algorithm, String input, SecretKey key,
                                 IvParameterSpec iv) throws NoSuchPaddingException, NoSuchAlgorithmException,
            InvalidAlgorithmParameterException, InvalidKeyException,
            BadPaddingException, IllegalBlockSizeException, UnsupportedEncodingException {

        Cipher cipher = Cipher.getInstance(algorithm);
        cipher.init(Cipher.ENCRYPT_MODE, key, iv);
        byte[] cipherText = cipher.doFinal(input.getBytes("UTF-8"));
        return Base64.getEncoder()
                .encodeToString(cipherText);
    }

    public static String decrypt(String algorithm, String cipherText, SecretKey key,
                                 IvParameterSpec iv) throws NoSuchPaddingException, NoSuchAlgorithmException,
            InvalidAlgorithmParameterException, InvalidKeyException,
            BadPaddingException, IllegalBlockSizeException, UnsupportedEncodingException {

        Cipher cipher = Cipher.getInstance(algorithm);
        cipher.init(Cipher.DECRYPT_MODE, key, iv);
        byte[] plainText = cipher.doFinal(Base64.getDecoder()
                .decode(cipherText));
        return new String(plainText, "UTF-8");
    }

    public static boolean isEmpty(String s) {
        return s == null || s.isEmpty();
    }

    public static Integer getInt(String s) {
        try {
            return Integer.valueOf(s);
        } catch (Exception e) {
            return null;
        }
    }

    public static void main(String[] args) throws Exception {
        String input = "abc你好";
        String pass = "mypass";
        String salt = "hi-test";
        String iv = Tool.generateIvBase64();
        System.out.println("iv: " + iv);
        SecretKey key = Tool.getKeyFromPassword(pass, salt);
        IvParameterSpec ivParameterSpec = Tool.getIvFromBase64(iv);
        String algorithm = "AES/CBC/PKCS5Padding";
        String cipherText = Tool.encrypt(algorithm, input, key, ivParameterSpec);
        String plainText = Tool.decrypt(algorithm, cipherText, key, ivParameterSpec);
        System.out.println(cipherText);
        System.out.println(plainText);
        SecretKey badKey = Tool.getKeyFromPassword("aaaa", salt);
        try {
            String badText = Tool.decrypt(algorithm, cipherText, badKey, ivParameterSpec);
        } catch (Exception e) {
            System.out.println("bad key");
        }

    }
}
