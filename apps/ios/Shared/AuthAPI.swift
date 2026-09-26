import Foundation

struct AuthAPI {
    static func configuration() async throws -> [String:Any] {
        let (data,response)=try await URLSession.shared.data(from:URL(string:Pilot.origin+"/api/v1/config")!)
        guard (response as? HTTPURLResponse)?.statusCode==200,let config=try JSONSerialization.jsonObject(with:data) as? [String:Any] else{throw QueueError.message("Lectic is unavailable. Your pending shares stay on this phone.")}
        return config
    }
    static func exchange(code:String, verifier:String) async throws {
        let config=try await configuration()
        try await token(config:config,grant:"pkce",body:["auth_code":code,"code_verifier":verifier])
    }
    static func refresh() async throws {
        guard let refresh=SecureSession.load()?["refresh_token"] as? String else{return}
        let config=try await configuration()
        try await token(config:config,grant:"refresh_token",body:["refresh_token":refresh])
    }
    static func token(config:[String:Any],grant:String,body:[String:String]) async throws {
        guard let base=config["supabaseUrl"] as? String,let key=config["publishableKey"] as? String,!base.isEmpty else{throw QueueError.message("Sign-in has not been configured for this pilot yet.")}
        var request=URLRequest(url:URL(string:base+"/auth/v1/token?grant_type="+grant)!)
        request.httpMethod="POST";request.setValue(key,forHTTPHeaderField:"apikey");request.setValue("application/json",forHTTPHeaderField:"Content-Type")
        request.httpBody=try JSONSerialization.data(withJSONObject:body)
        let (data,response)=try await URLSession.shared.data(for:request)
        guard (response as? HTTPURLResponse)?.statusCode==200 else{throw QueueError.message("Please sign in again. Pending shares are safe.")}
        try SecureSession.save(data)
    }
}
