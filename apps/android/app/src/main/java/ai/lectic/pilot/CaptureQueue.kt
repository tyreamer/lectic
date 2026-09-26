package ai.lectic.pilot

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import android.util.AtomicFile
import androidx.work.*
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID
import java.util.concurrent.TimeUnit

object CaptureQueue {
    private fun root(context:Context)=File(context.filesDir,"pending").apply{mkdirs()}
    fun folder(context:Context,id:String):File { UUID.fromString(id);return File(root(context),id).apply{mkdirs()} }
    @Synchronized fun save(context:Context,record:JSONObject) {
        val file=AtomicFile(File(folder(context,record.getString("id")),"capture.json"))
        val stream=file.startWrite()
        try{stream.write(record.toString().toByteArray());file.finishWrite(stream)}catch(e:Exception){file.failWrite(stream);throw e}
    }
    fun all(context:Context):List<JSONObject> = root(context).listFiles()?.mapNotNull { dir->runCatching{JSONObject(File(dir,"capture.json").readText())}.getOrNull() }?.sortedByDescending{it.optLong("created")}?:emptyList()
    fun load(context:Context,id:String)=JSONObject(File(folder(context,id),"capture.json").readText())
    private fun record(title:String)=JSONObject().put("id",UUID.randomUUID().toString()).put("created",System.currentTimeMillis()).put("title",title.take(120)).put("state","Saved on this phone")
    fun text(context:Context,text:String):String {
        require(text.isNotBlank()&&text.toByteArray().size<=200000){"Share less text at a time."}
        val record=record(text).put("text",text);save(context,record);enqueue(context,record.getString("id"));return record.getString("id")
    }
    fun file(context:Context,uri:Uri):String {
        require(uri.scheme=="content"){"Only a shared file can be saved."}
        var name="Shared file"
        context.contentResolver.query(uri,arrayOf(OpenableColumns.DISPLAY_NAME),null,null,null)?.use { cursor->if(cursor.moveToFirst())name=cursor.getString(0) }
        val record=record(name).put("filename",name)
        val original=File(folder(context,record.getString("id")),"original")
        var total=0L
        try {
            context.contentResolver.openInputStream(uri)!!.use { input->FileOutputStream(original).use { output->
                val buffer=ByteArray(65536)
                while(true){val count=input.read(buffer);if(count<0)break;total+=count;require(total<=100L*1024*1024){"Choose a file under 100 MB."};output.write(buffer,0,count)}
                output.fd.sync()
            }}
            require(total>0){"This file is empty."}
            record.put("size",total);save(context,record);enqueue(context,record.getString("id"));return record.getString("id")
        }catch(e:Exception){original.delete();throw e}
    }
    fun enqueue(context:Context,id:String) {
        val work=OneTimeWorkRequestBuilder<UploadWorker>().setInputData(workDataOf("id" to id))
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL,30,TimeUnit.SECONDS).build()
        WorkManager.getInstance(context).enqueueUniqueWork("capture-"+id,ExistingWorkPolicy.KEEP,work)
    }
    fun retry(context:Context){all(context).filter{it.optString("state")!="Uploaded"}.forEach{enqueue(context,it.getString("id"))}}
}

class UploadWorker(context:Context,parameters:WorkerParameters):CoroutineWorker(context,parameters) {
    override suspend fun doWork():Result = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
        val id=inputData.getString("id")?:return@withContext Result.failure()
        val record=CaptureQueue.load(applicationContext,id)
        if(record.optString("state")=="Uploaded")return@withContext Result.success()
        try {
            val token=Network.accessToken(applicationContext)
            val headers=mapOf("Authorization" to "Bearer $token","Idempotency-Key" to id)
            record.put("state","Uploading");CaptureQueue.save(applicationContext,record)
            if(!record.has("capture_id")){
                val body=JSONObject().put("title",record.getString("title"))
                if(record.has("filename"))body.put("kind","upload").put("filename",record.getString("filename")).put("size",record.getLong("size"))
                else {
                    val text=record.getString("text");val match=android.util.Patterns.WEB_URL.matcher(text)
                    if(match.find()&&match.group().startsWith("http"))body.put("kind","url").put("url",match.group()).put("text",text)
                    else body.put("kind","note").put("text",text)
                }
                val accepted=Network.request(BuildConfig.LECTIC_ORIGIN+"/api/v1/captures","POST",body,headers)
                record.put("capture_id",accepted.getString("capture_id")).put("operation_id",accepted.getString("operation_id"));CaptureQueue.save(applicationContext,record)
            }
            if(record.has("filename")) {
                val connection=URL(BuildConfig.LECTIC_ORIGIN+"/api/v1/captures/"+record.getString("capture_id")+"/content").openConnection() as HttpURLConnection
                try {
                    connection.requestMethod="PUT";connection.doOutput=true;connection.connectTimeout=15000;connection.readTimeout=120000;connection.instanceFollowRedirects=false
                    connection.setRequestProperty("Authorization","Bearer $token");connection.setRequestProperty("Content-Type","application/octet-stream")
                    connection.setFixedLengthStreamingMode(record.getLong("size"))
                    File(CaptureQueue.folder(applicationContext,id),"original").inputStream().use{input->connection.outputStream.use{output->input.copyTo(output)}}
                    if(connection.responseCode !in 200..299)throw ApiError(connection.responseCode)
                }finally{connection.disconnect()}
            }
            record.put("state","Uploaded");CaptureQueue.save(applicationContext,record)
            File(CaptureQueue.folder(applicationContext,id),"original").delete()
            Result.success()
        }catch(e:Exception){
            record.put("state",if(e is ApiError&&e.status==401)"Saved — sign in again" else "Saved — retry needed");CaptureQueue.save(applicationContext,record)
            if(e is ApiError&&e.status in listOf(401,403,413,422))Result.failure()
            else if(runAttemptCount<5)Result.retry() else Result.failure()
        }
    }
}
