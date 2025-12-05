import discord
import asyncio
import logging
from typing import Dict, Any, Optional, List
import re

logger = logging.getLogger(__name__)


class CommandHandler:
    def __init__(self, bot, db_manager, encryption_manager):
        self.bot = bot
        self.db_manager = db_manager
        self.encryption_manager = encryption_manager
        self.user_states = {}  # State machine storage
        self.timeout_duration = 120  # 120 seconds timeout

    async def handle_message(self, message):
        """Handle incoming messages and route to appropriate command handlers"""
        content = message.content.strip()

        # Check if user is in a state flow
        if message.author.id in self.user_states:
            await self.handle_state_response(message)
            return

        # Parse command
        if content.startswith("!"):
            parts = content[1:].split(maxsplit=1)
            command = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            # Route to appropriate command
            if command == "new":
                await self.handle_new_command(message, args)
            elif command == "get":
                await self.handle_get_command(message, args)
            elif command == "list":
                await self.handle_list_command(message)
            elif command == "delete":
                await self.handle_delete_command(message, args)
            elif command == "update":
                await self.handle_update_command(message, args)
            elif command == "help":
                await self.handle_help_command(message)

    async def handle_new_command(self, message, args):
        """Handle !new command - both single and multi-step paths"""
        user_id = message.author.id

        if args:
            # Path B: Service name provided
            service_name = args.strip()
            unique_service_name = await self.generate_unique_service_name(
                user_id, service_name
            )

            # Initialize state for username and password collection
            self.user_states[user_id] = {
                "command": "new",
                "step": "awaiting_username",
                "service_name": unique_service_name,
                "username": None,
                "message_ids": [message.id],
                "timeout_task": None,
            }

            await self.set_timeout(user_id)
            await message.channel.send(
                f"📝 **Username for {unique_service_name}?**\n"
                f"Type 'skip' or 'N/A' to omit username."
            )
        else:
            # Path A: No service name provided
            self.user_states[user_id] = {
                "command": "new",
                "step": "awaiting_service",
                "service_name": None,
                "username": None,
                "message_ids": [message.id],
                "timeout_task": None,
            }

            await self.set_timeout(user_id)
            await message.channel.send("🔍 **Service Name?**")

    async def handle_get_command(self, message, args):
        """Handle !get command - retrieve credentials via DM"""
        if not args:
            await message.channel.send(
                "❌ Please specify a service name: `!get <service_name>`"
            )
            return

        service_name = args.strip()
        user_id = message.author.id

        # Search for the service
        password_entry = await self.db_manager.get_password(user_id, service_name)

        if not password_entry:
            # Try partial search
            matches = await self.db_manager.search_services(user_id, service_name)
            if matches:
                match_list = "\n".join(
                    [f"• {match['service_name']}" for match in matches[:5]]
                )
                await message.channel.send(
                    f"❌ Exact match not found. Did you mean:\n{match_list}"
                )
            else:
                await message.channel.send("❌ No service found with that name.")
            return

        try:
            # Decrypt the password
            decrypted_data = self.encryption_manager.decrypt(
                password_entry["encrypted_payload"]
            )

            # Send via DM
            embed = discord.Embed(
                title=f"🔐 Credentials for {password_entry['service_name']}",
                color=discord.Color.green(),
            )
            embed.add_field(
                name="Username",
                value=password_entry["username"] or "Not specified",
                inline=False,
            )
            embed.add_field(
                name="Password", value=f"||{decrypted_data}||", inline=False
            )
            embed.add_field(
                name="Created",
                value=password_entry["created_at"].strftime("%Y-%m-%d %H:%M"),
                inline=False,
            )

            await message.author.send(embed=embed)
            await message.channel.send("✅ Credentials sent to your DMs!")

        except Exception as e:
            await message.channel.send(
                "❌ Failed to retrieve credentials. Please try again."
            )

    async def handle_list_command(self, message):
        """Handle !list command - show all stored services"""
        user_id = message.author.id
        services = await self.db_manager.get_all_user_services(user_id)

        if not services:
            await message.channel.send("📭 You don't have any stored passwords yet.")
            return

        # Create embed with service list
        embed = discord.Embed(
            title="🔑 Your Stored Services", color=discord.Color.blue()
        )

        # Group services by name
        service_groups = {}
        for service in services:
            name = service["service_name"]
            if name not in service_groups:
                service_groups[name] = []
            service_groups[name].append(service)

        for service_name, entries in service_groups.items():
            if len(entries) == 1:
                entry = entries[0]
                username_info = f"({entry['username']})" if entry["username"] else ""
                created_date = entry["created_at"].strftime("%m/%d/%Y")
                embed.add_field(
                    name=f"📌 {service_name}",
                    value=f"{username_info} - Created: {created_date}",
                    inline=False,
                )
            else:
                # Multiple entries with same name
                for i, entry in enumerate(entries, 1):
                    username_info = (
                        f"({entry['username']})" if entry["username"] else ""
                    )
                    created_date = entry["created_at"].strftime("%m/%d/%Y")
                    embed.add_field(
                        name=f"📌 {service_name} #{i}",
                        value=f"{username_info} - Created: {created_date}",
                        inline=False,
                    )

        embed.set_footer(text=f"Total: {len(services)} service(s)")
        await message.channel.send(embed=embed)

    async def handle_delete_command(self, message, args):
        """Handle !delete command - remove entry with confirmation"""
        if not args:
            await message.channel.send(
                "❌ Please specify a service name: `!delete <service_name>`"
            )
            return

        service_name = args.strip()
        user_id = message.author.id

        # Search for the service
        password_entry = await self.db_manager.get_password(user_id, service_name)

        if not password_entry:
            # Try partial search
            matches = await self.db_manager.search_services(user_id, service_name)
            if matches:
                match_list = "\n".join(
                    [f"• {match['service_name']}" for match in matches[:5]]
                )
                await message.channel.send(
                    f"❌ Exact match not found. Did you mean:\n{match_list}"
                )
            else:
                await message.channel.send("❌ No service found with that name.")
            return

        # Initialize confirmation state
        self.user_states[user_id] = {
            "command": "delete",
            "step": "awaiting_confirmation",
            "service_name": password_entry["service_name"],
            "message_ids": [message.id],
            "timeout_task": None,
        }

        await self.set_timeout(user_id)

        embed = discord.Embed(
            title="⚠️ Confirm Deletion",
            description=f"Are you sure you want to delete the password for **{password_entry['service_name']}**?",
            color=discord.Color.red(),
        )
        embed.add_field(
            name="Username",
            value=password_entry["username"] or "Not specified",
            inline=False,
        )
        embed.set_footer(text="Type 'yes' to confirm or 'no' to cancel")

        await message.channel.send(embed=embed)

    async def handle_update_command(self, message, args):
        """Handle !update command - modify existing entry"""
        if not args:
            await message.channel.send(
                "❌ Please specify a service name: `!update <service_name>`"
            )
            return

        service_name = args.strip()
        user_id = message.author.id

        # Search for the service
        password_entry = await self.db_manager.get_password(user_id, service_name)

        if not password_entry:
            # Try partial search
            matches = await self.db_manager.search_services(user_id, service_name)
            if matches:
                match_list = "\n".join(
                    [f"• {match['service_name']}" for match in matches[:5]]
                )
                await message.channel.send(
                    f"❌ Exact match not found. Did you mean:\n{match_list}"
                )
            else:
                await message.channel.send("❌ No service found with that name.")
            return

        # Initialize field selection state
        self.user_states[user_id] = {
            "command": "update",
            "step": "awaiting_field",
            "service_name": password_entry["service_name"],
            "username": password_entry["username"],
            "message_ids": [message.id],
            "timeout_task": None,
        }

        await self.set_timeout(user_id)

        embed = discord.Embed(
            title="🔧 Update Service",
            description=f"What would you like to update for **{password_entry['service_name']}**?",
            color=discord.Color.orange(),
        )
        embed.add_field(
            name="Current Username",
            value=password_entry["username"] or "Not specified",
            inline=False,
        )
        embed.add_field(
            name="Options",
            value="• `service` - Update service name\n• `username` - Update username\n• `password` - Update password",
            inline=False,
        )
        embed.set_footer(text="Type your choice (service/username/password)")

        await message.channel.send(embed=embed)

    async def handle_help_command(self, message):
        """Handle !help command - show usage information"""
        embed = discord.Embed(
            title="🤖 Password Bot Help",
            description="Secure password management for Discord",
            color=discord.Color.purple(),
        )

        embed.add_field(
            name="📝 Add Password",
            value="`!new` - Start multi-step password creation\n`!new <service>` - Quick add with service name",
            inline=False,
        )

        embed.add_field(
            name="🔍 Retrieve Password",
            value="`!get <service>` - Get credentials via DM",
            inline=False,
        )

        embed.add_field(
            name="📋 List Services",
            value="`!list` - Show all stored services",
            inline=False,
        )

        embed.add_field(
            name="🗑️ Delete Password",
            value="`!delete <service>` - Remove a stored password",
            inline=False,
        )

        embed.add_field(
            name="🔧 Update Password",
            value="`!update <service>` - Modify existing entry",
            inline=False,
        )

        embed.add_field(
            name="⏱️ Timeout",
            value="All multi-step operations timeout after 120 seconds",
            inline=False,
        )

        embed.set_footer(text="All sensitive data is encrypted and sent via DM")

        await message.channel.send(embed=embed)

    async def handle_state_response(self, message):
        """Handle responses in multi-step command flows"""
        user_id = message.author.id
        content = message.content.strip()

        if user_id not in self.user_states:
            return

        state = self.user_states[user_id]

        try:
            # Cancel existing timeout
            if state["timeout_task"]:
                state["timeout_task"].cancel()

            # Route based on current step
            if state["step"] == "awaiting_service":
                await self.handle_service_response(message, content)
            elif state["step"] == "awaiting_username":
                await self.handle_username_response(message, content)
            elif state["step"] == "awaiting_password":
                await self.handle_password_response(message, content)
            elif state["step"] == "awaiting_confirmation":
                await self.handle_confirmation_response(message, content)
            elif state["step"] == "awaiting_field":
                await self.handle_field_response(message, content)
            elif state["step"] == "awaiting_new_value":
                await self.handle_new_value_response(message, content)

        except Exception as e:
            await message.channel.send("❌ An error occurred. Please try again.")
            await self.cleanup_user_state(user_id)

    async def handle_service_response(self, message, service_name):
        """Handle service name response in !new command"""
        user_id = message.author.id
        unique_service_name = await self.generate_unique_service_name(
            user_id, service_name
        )

        self.user_states[user_id]["service_name"] = unique_service_name
        self.user_states[user_id]["step"] = "awaiting_username"

        await self.set_timeout(user_id)
        await message.channel.send(
            f"📝 **Username for {unique_service_name}?**\n"
            f"Type 'skip' or 'N/A' to omit username."
        )

    async def handle_username_response(self, message, username):
        """Handle username response in !new command"""
        user_id = message.author.id

        if username.lower() in ["skip", "n/a", ""]:
            username = None

        self.user_states[user_id]["username"] = username
        self.user_states[user_id]["step"] = "awaiting_password"

        await self.set_timeout(user_id)
        await message.channel.send(
            "🔒 **Password?** (This message will be deleted after saving)"
        )

    async def handle_password_response(self, message, password):
        """Handle password response in !new command"""
        user_id = message.author.id
        state = self.user_states[user_id]

        try:
            # Encrypt the password
            encrypted_payload = self.encryption_manager.encrypt(password)

            # Save to database
            await self.db_manager.add_password(
                user_id, state["service_name"], state["username"], encrypted_payload
            )

            # Delete the password message for security
            try:
                await message.delete()
            except:
                pass  # Ignore if we can't delete the message

            await message.channel.send(
                f"✅ Password for **{state['service_name']}** saved successfully!"
            )

        except Exception as e:
            await message.channel.send("❌ Failed to save password. Please try again.")

        await self.cleanup_user_state(user_id)

    async def handle_confirmation_response(self, message, response):
        """Handle confirmation response in !delete command"""
        user_id = message.author.id
        state = self.user_states[user_id]

        if response.lower() in ["yes", "y", "confirm"]:
            # Delete the password
            success = await self.db_manager.delete_password(
                user_id, state["service_name"]
            )

            if success:
                await message.channel.send(
                    f"✅ Password for **{state['service_name']}** deleted successfully!"
                )
            else:
                await message.channel.send(
                    "❌ Failed to delete password. Please try again."
                )
        else:
            await message.channel.send("❌ Deletion cancelled.")

        await self.cleanup_user_state(user_id)

    async def handle_field_response(self, message, field):
        """Handle field selection response in !update command"""
        user_id = message.author.id
        field = field.lower()

        if field not in ["service", "username", "password"]:
            await message.channel.send(
                "❌ Invalid choice. Please choose: service, username, or password"
            )
            await self.set_timeout(user_id)
            return

        self.user_states[user_id]["field_to_update"] = field
        self.user_states[user_id]["step"] = "awaiting_new_value"

        await self.set_timeout(user_id)

        if field == "service":
            await message.channel.send("📝 **New service name?**")
        elif field == "username":
            await message.channel.send(
                "📝 **New username?** (Type 'skip' or 'N/A' to omit)"
            )
        elif field == "password":
            await message.channel.send(
                "🔒 **New password?** (This message will be deleted after saving)"
            )

    async def handle_new_value_response(self, message, new_value):
        """Handle new value response in !update command"""
        user_id = message.author.id
        state = self.user_states[user_id]
        field = state["field_to_update"]

        try:
            if field == "password":
                # Encrypt the new password
                encrypted_payload = self.encryption_manager.encrypt(new_value)
                success = await self.db_manager.update_password(
                    user_id, state["service_name"], field, None, encrypted_payload
                )
                # Delete the password message for security
                try:
                    await message.delete()
                except:
                    pass
            else:
                if field == "username" and new_value.lower() in ["skip", "n/a", ""]:
                    new_value = None

                success = await self.db_manager.update_password(
                    user_id, state["service_name"], field, new_value
                )

            if success:
                await message.channel.send(
                    f"✅ **{field.capitalize()}** updated successfully!"
                )
            else:
                await message.channel.send("❌ Failed to update. Please try again.")

        except Exception as e:
            await message.channel.send("❌ An error occurred while updating.")

        await self.cleanup_user_state(user_id)

    async def generate_unique_service_name(self, user_id, base_name):
        """Generate a unique service name by appending (1), (2), etc. if needed"""
        existing_services = await self.db_manager.get_user_service_names(user_id)

        if base_name not in existing_services:
            return base_name

        counter = 1
        while f"{base_name}({counter})" in existing_services:
            counter += 1

        return f"{base_name}({counter})"

    async def set_timeout(self, user_id):
        """Set a timeout for user input"""
        if user_id in self.user_states:
            task = asyncio.create_task(self.timeout_handler(user_id))
            self.user_states[user_id]["timeout_task"] = task

    async def timeout_handler(self, user_id):
        """Handle timeout for user input"""
        await asyncio.sleep(self.timeout_duration)

        if user_id in self.user_states:
            try:
                user = self.bot.get_user(user_id)
                if user:
                    await user.send("⏰ Operation timed out after 120 seconds.")
            except:
                pass  # Ignore if we can't send DM

            await self.cleanup_user_state(user_id)

    async def cleanup_user_state(self, user_id, timeout=False):
        """Clean up user state and cancel timeout"""
        if user_id in self.user_states:
            state = self.user_states[user_id]

            # Cancel timeout task
            if state["timeout_task"]:
                state["timeout_task"].cancel()

            # Remove from states
            del self.user_states[user_id]
