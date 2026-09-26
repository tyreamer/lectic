package ai.lectic.pilot

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.*
import androidx.core.content.IntentCompat
import kotlinx.coroutines.*

class MainActivity:Activity() {
    private val scope=CoroutineScope(SupervisorJob()+Dispatchers.Main)
    private lateinit var list:LinearLayout
    private lateinit var status:TextView
    override fun onCreate(state:Bundle?){super.onCreate(state);layout();if(state==null)handle(intent);refresh()}
    override fun onNewIntent(intent:Intent){super.onNewIntent(intent);setIntent(intent);handle(intent)}
    override fun onResume(){super.onResume();if(::list.isInitialized)refresh()}
    override fun onDestroy(){scope.cancel();super.onDestroy()}
    private fun layout(){
        val root=LinearLayout(this).apply{orientation=LinearLayout.VERTICAL;setPadding(32,56,32,24)}
        root.addView(TextView(this).apply{text="Lectic";textSize=36f})
        root.addView(TextView(this).apply{text="Share from any app → Lectic";textSize=17f;setPadding(0,16,0,24)})
        status=TextView(this);root.addView(status)
        root.addView(Button(this).apply{text="Sign in with Google";setOnClickListener{login()}})
        root.addView(Button(this).apply{text="Open my library ↗";setOnClickListener{startActivity(Intent(Intent.ACTION_VIEW,Uri.parse(BuildConfig.LECTIC_ORIGIN)))}})
        root.addView(Button(this).apply{text="Retry pending uploads";setOnClickListener{CaptureQueue.retry(this@MainActivity);refresh()}})
        list=LinearLayout(this).apply{orientation=LinearLayout.VERTICAL}
        root.addView(ScrollView(this).apply{addView(list)},LinearLayout.LayoutParams(-1,0,1f));setContentView(root)
    }
    private fun refresh(){list.removeAllViews();CaptureQueue.all(this).forEach{row->list.addView(TextView(this).apply{text=row.getString("title")+"\n"+row.getString("state");textSize=15f;setPadding(0,20,0,20)})}}
    private fun login(){scope.launch{try{val uri=withContext(Dispatchers.IO){Network.startLogin(this@MainActivity)};startActivity(Intent(Intent.ACTION_VIEW,uri))}catch(e:Exception){show(e.message?:"Sign-in unavailable")}}}
    private fun handle(intent:Intent){
        if(intent.action==Intent.ACTION_VIEW&&intent.data?.scheme=="lectic"){
            scope.launch{try{withContext(Dispatchers.IO){Network.finishLogin(this@MainActivity,intent.data!!)};CaptureQueue.retry(this@MainActivity);status.text="Signed in";refresh()}catch(e:Exception){show(e.message?:"Please sign in again")}};return
        }
        if(intent.action !in listOf(Intent.ACTION_SEND,Intent.ACTION_SEND_MULTIPLE))return
        val uris=mutableListOf<Uri>()
        IntentCompat.getParcelableExtra(intent,Intent.EXTRA_STREAM,Uri::class.java)?.let{uris.add(it)}
        IntentCompat.getParcelableArrayListExtra(intent,Intent.EXTRA_STREAM,Uri::class.java)?.let{uris.addAll(it)}
        intent.clipData?.let{clip->for(i in 0 until clip.itemCount)clip.getItemAt(i).uri?.let{uris.add(it)}}
        val text=intent.getCharSequenceExtra(Intent.EXTRA_TEXT)?.toString()
        AlertDialog.Builder(this).setTitle("Save to Lectic?").setMessage(if(uris.isNotEmpty())"${uris.distinct().size} file(s) will be kept in your Inbox." else text?.take(400)?:"No content was supplied.")
            .setNegativeButton("Cancel"){_,_->finish()}.setPositiveButton("Save"){_,_->
                scope.launch {
                    status.text="Saving on this phone…"
                    try {
                        withContext(Dispatchers.IO){
                            require(uris.distinct().size<=20){"Share up to 20 files at a time."}
                            if(!text.isNullOrBlank())CaptureQueue.text(this@MainActivity,text)
                            uris.distinct().forEach{CaptureQueue.file(this@MainActivity,it)}
                        }
                        status.text="Saved on this phone. Uploads continue in the background.";refresh()
                    }catch(e:Exception){show((e.message?:"Could not save this share")+". Any saved items remain in Lectic.");refresh()}
                }
            }.show()
    }
    private fun show(message:String){status.text=message;AlertDialog.Builder(this).setTitle("Lectic").setMessage(message).setPositiveButton("OK",null).show()}
}
