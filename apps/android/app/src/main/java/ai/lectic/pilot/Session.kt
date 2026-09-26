package ai.lectic.pilot

import android.content.Context
import android.net.Uri
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.security.KeyStore
import java.security.MessageDigest
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

object Vault {
    private const val alias="lectic-session"
    private fun key():SecretKey {
        val store=KeyStore.getInstance("AndroidKeyStore").apply{load(null)}
        (store.getKey(alias,null) as? SecretKey)?.let{return it}
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(alias,KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    @Synchronized fun put(context:Context,name:String,value:String) {
        val cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key())
        val encoded=Base64.encodeToString(cipher.iv+cipher.doFinal(value.toByteArray()),Base64.NO_WRAP)
        check(context.getSharedPreferences("vault",Context.MODE_PRIVATE).edit().putString(name,encoded).commit())
    }
    @Synchronized fun get(context:Context,name:String):String? {
        val encoded=context.getSharedPreferences("vault",Context.MODE_PRIVATE).getString(name,null)?:return null
        return runCatching {
            val bytes=Base64.decode(encoded,Base64.NO_WRAP)
            val cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,key(),GCMParameterSpec(128,bytes.copyOfRange(0,12)))
            String(cipher.doFinal(bytes.copyOfRange(12,bytes.size)))
        }.getOrNull()
    }
}

class ApiError(val status:Int):Exception(if(status==401)"Sign in again. Your pending shares are safe." else "Upload paused ($status). Your pending shares are safe.")

object Network {
    fun request(url:String,method:String="GET",body:JSONObject?=null,headers:Map<String,String> = emptyMap()):JSONObject {
        val connection=URL(url).openConnection() as HttpURLConnection
        try {
            connection.connectTimeout=15000;connection.readTimeout=45000;connection.instanceFollowRedirects=false
            connection.requestMethod=method
            headers.forEach{(k,v)->connection.setRequestProperty(k,v)}
            if(body!=null){connection.doOutput=true;connection.setRequestProperty("Content-Type","application/json");connection.outputStream.use{it.write(body.toString().toByteArray())}}
            if(connection.responseCode !in 200..299)throw ApiError(connection.responseCode)
            val text=connection.inputStream.bufferedReader().use{it.readText()}
            require(text.length<1_000_000)
            return JSONObject(text)
        }finally{connection.disconnect()}
    }
    fun config()=request(BuildConfig.LECTIC_ORIGIN+"/api/v1/config")
    fun startLogin(context:Context):Uri {
        val config=config();val base=config.getString("supabaseUrl");require(base.startsWith("https://")){"Pilot sign-in is not configured yet."}
        val bytes=ByteArray(32).also{SecureRandom().nextBytes(it)}
        val verifier=Base64.encodeToString(bytes,Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)
        Vault.put(context,"verifier",verifier)
        val challenge=Base64.encodeToString(MessageDigest.getInstance("SHA-256").digest(verifier.toByteArray()),Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)
        return Uri.parse(base+"/auth/v1/authorize").buildUpon().appendQueryParameter("provider","google")
            .appendQueryParameter("redirect_to","lectic://auth").appendQueryParameter("code_challenge",challenge).appendQueryParameter("code_challenge_method","s256").build()
    }
    fun finishLogin(context:Context,uri:Uri) {
        require(uri.scheme=="lectic"&&uri.host=="auth")
        val code=uri.getQueryParameter("code")?:error("Sign-in was not completed.")
        val verifier=Vault.get(context,"verifier")?:error("Start sign-in again.")
        token(context,"pkce",JSONObject().put("auth_code",code).put("code_verifier",verifier))
        Vault.put(context,"verifier","")
    }
    @Synchronized fun accessToken(context:Context):String {
        val session=JSONObject(Vault.get(context,"session")?:throw ApiError(401))
        if(session.optLong("expires_at",0)>System.currentTimeMillis()/1000+120)return session.getString("access_token")
        return token(context,"refresh_token",JSONObject().put("refresh_token",session.getString("refresh_token"))).getString("access_token")
    }
    private fun token(context:Context,grant:String,body:JSONObject):JSONObject {
        val config=config()
        val session=request(config.getString("supabaseUrl")+"/auth/v1/token?grant_type="+grant,"POST",body,mapOf("apikey" to config.getString("publishableKey")))
        if(!session.has("expires_at"))session.put("expires_at",System.currentTimeMillis()/1000+session.optLong("expires_in",3600))
        Vault.put(context,"session",session.toString());return session
    }
}
